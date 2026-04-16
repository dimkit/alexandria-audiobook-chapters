"""ProjectManager behavior tests grouped by domain."""

import json
import os
import tempfile
import time
import threading
import unittest
import zipfile
from unittest.mock import patch

import numpy as np
import soundfile as sf
from types import SimpleNamespace
from pydub import AudioSegment

import project as project_module
import project_core.mixins.chunk_store as chunk_store_module
from project import ProjectManager

class ChunkBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = self.temp_dir.name
        os.makedirs(os.path.join(self.root_dir, "voicelines"), exist_ok=True)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)

        with open(os.path.join(self.root_dir, "annotated_script.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": [], "dictionary": []}, f)

        self.manager = ProjectManager(self.root_dir)

    def tearDown(self):
        self.manager.shutdown_script_store(flush=True)
        self.temp_dir.cleanup()

    def _load_chunk_backup(self, key):
        payload = self.manager.script_store.load_project_document(key) or {}
        return payload.get("chunks")

    def test_chunk_backups_keep_latest_and_preserve_most_audio_version(self):
        low_audio_chunks = [
            {"id": 0, "uid": "a", "speaker": "NARRATOR", "text": "One", "instruct": "", "status": "done", "audio_path": "voicelines/a.mp3"},
            {"id": 1, "uid": "b", "speaker": "NARRATOR", "text": "Two", "instruct": "", "status": "pending", "audio_path": None},
        ]
        high_audio_chunks = [
            {"id": 0, "uid": "a", "speaker": "NARRATOR", "text": "One", "instruct": "", "status": "done", "audio_path": "voicelines/a.mp3"},
            {"id": 1, "uid": "b", "speaker": "NARRATOR", "text": "Two", "instruct": "", "status": "done", "audio_path": "voicelines/b.mp3"},
        ]
        regressed_chunks = [
            {"id": 0, "uid": "a", "speaker": "NARRATOR", "text": "One revised", "instruct": "", "status": "done", "audio_path": "voicelines/a.mp3"},
            {"id": 1, "uid": "b", "speaker": "NARRATOR", "text": "Two revised", "instruct": "", "status": "pending", "audio_path": None},
        ]

        self.manager.save_chunks(low_audio_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_latest"), low_audio_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_most_audio"), low_audio_chunks)

        self.manager.save_chunks(high_audio_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_latest"), high_audio_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_most_audio"), high_audio_chunks)

        self.manager.save_chunks(regressed_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_latest"), regressed_chunks)
        self.assertEqual(self._load_chunk_backup("chunk_backup_most_audio"), high_audio_chunks)

class TranscriptionCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = self.temp_dir.name
        os.makedirs(os.path.join(self.root_dir, "voicelines"), exist_ok=True)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)

        with open(os.path.join(self.root_dir, "annotated_script.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": [], "dictionary": []}, f)

        self.manager = ProjectManager(self.root_dir)

    def tearDown(self):
        self.manager.shutdown_script_store(flush=True)
        self.temp_dir.cleanup()

    def _write_wav(self, relative_path, duration_seconds):
        full_path = os.path.join(self.root_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        sample_rate = 24000
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
        sf.write(full_path, samples, sample_rate)
        return full_path

    def test_transcribe_audio_path_reuses_cached_transcript_for_same_file(self):
        self._write_wav("voicelines/example.wav", 1.0)

        class FakeEngine:
            def __init__(self):
                self.calls = 0
            def transcribe_file(self, full_path):
                self.calls += 1
                return {"text": "Cached transcript."}

        fake_engine = FakeEngine()
        self.manager.get_asr_engine = lambda: fake_engine

        first = self.manager.transcribe_audio_path("voicelines/example.wav")
        second = self.manager.transcribe_audio_path("voicelines/example.wav")

        self.assertEqual(fake_engine.calls, 1)
        self.assertEqual(first["text"], "Cached transcript.")
        self.assertFalse(first["cached"])
        self.assertEqual(second["text"], "Cached transcript.")
        self.assertTrue(second["cached"])

    def test_transcribe_audio_path_reuses_cache_for_matching_filename_and_filesize(self):
        self._write_wav("voicelines/discarded/shared.wav", 1.0)
        self._write_wav("voicelines/shared.wav", 1.0)

        class FakeEngine:
            def __init__(self):
                self.calls = 0
            def transcribe_file(self, full_path):
                self.calls += 1
                return {"text": "Shared transcript."}

        fake_engine = FakeEngine()
        self.manager.get_asr_engine = lambda: fake_engine

        first = self.manager.transcribe_audio_path("voicelines/discarded/shared.wav")
        second = self.manager.transcribe_audio_path("voicelines/shared.wav")

        self.assertEqual(fake_engine.calls, 1)
        self.assertEqual(first["text"], "Shared transcript.")
        self.assertFalse(first["cached"])
        self.assertEqual(second["text"], "Shared transcript.")
        self.assertTrue(second["cached"])

    def test_resets_interrupted_generating_chunk_without_valid_audio(self):
        chunks = [{
            "id": 0,
            "speaker": "Narrator",
            "text": "One two three four five six.",
            "instruct": "",
            "status": "generating",
            "audio_path": "voicelines/missing.wav",
            "audio_validation": None,
            "auto_regen_count": 0,
            "generation_token": "abc",
        }]
        self.manager.save_chunks(chunks)

        outcome = self.manager.recover_interrupted_generating_chunks()
        recovered = self.manager.load_chunks()

        self.assertEqual(outcome, {"recovered": 0, "reset": 1})
        self.assertEqual(recovered[0]["status"], "pending")
        self.assertNotIn("generation_token", recovered[0])

    def test_collect_voice_suggestion_context_uses_story_order_and_target_chars(self):
        with open(os.path.join(self.root_dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"input_file_path": os.path.join(self.root_dir, "story.txt")}, f)
        with open(os.path.join(self.root_dir, "story.txt"), "w", encoding="utf-8") as f:
            f.write(
                "Alice stepped into the hall.\n\n"
                "Bob answered from the stair.\n\n"
                "Alice spoke again near the window.\n\n"
                "Alice kept talking until the lamps burned low."
            )
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"generation": {"chunk_size": 20}}, f)

        context = self.manager.collect_voice_suggestion_context("Alice")

        self.assertEqual(context["target_chars"], 40)
        self.assertEqual(
            [item["text"] for item in context["paragraphs"]],
            [
                "Alice stepped into the hall.",
                "Alice spoke again near the window.",
            ],
        )
        self.assertGreaterEqual(context["context_chars"], 40)

    def test_build_voice_suggestion_prompt_places_prompt_after_context(self):
        with open(os.path.join(self.root_dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"input_file_path": os.path.join(self.root_dir, "story.txt")}, f)
        with open(os.path.join(self.root_dir, "story.txt"), "w", encoding="utf-8") as f:
            f.write("Alice laughed softly.\n\nAlice took a breath.")

        payload = self.manager.build_voice_suggestion_prompt(
            "Alice",
            'Return {"voice":"for {character_name}"}',
        )

        self.assertIn('Source paragraphs mentioning "Alice"', payload["prompt"])
        self.assertTrue(payload["prompt"].endswith('Return {"voice":"for Alice"}'))

    def test_voice_suggestion_falls_back_to_chunks_when_source_missing(self):
        with open(os.path.join(self.root_dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"input_file_path": os.path.join(self.root_dir, "missing.txt")}, f)
        chunks = [
            {"id": 0, "speaker": "Alice", "text": "Alice took a careful breath.", "chapter": "Chapter 1"},
            {"id": 1, "speaker": "Narrator", "text": "The room was silent."},
            {"id": 2, "speaker": "Alice", "text": "Alice spoke in a calm, steady tone.", "chapter": "Chapter 1"},
        ]
        self.manager.save_chunks(chunks)

        context = self.manager.collect_voice_suggestion_context("Alice", target_chars=30)
        payload = self.manager.build_voice_suggestion_prompt(
            "Alice",
            'Return {"voice":"for {character_name}"}',
        )

        self.assertEqual(context["context_source"], "chunks_fallback")
        self.assertIsNotNone(context["source_error"])
        self.assertGreaterEqual(len(context["paragraphs"]), 1)
        self.assertIn("Source document unavailable", payload["prompt"])
        self.assertIn('Fallback context from generated chunks mentioning "Alice"', payload["prompt"])
        self.assertTrue(payload["warning"])

    def test_render_prep_flag_persists_in_state(self):
        self.assertFalse(self.manager.is_render_prep_complete())

        self.assertTrue(self.manager.set_render_prep_complete(True))
        self.assertTrue(self.manager.is_render_prep_complete())

        state_path = os.path.join(self.root_dir, "state.json")
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertTrue(state["render_prep_complete"])

    def test_auto_regen_retry_attempts_uses_positive_config_value(self):
        config_path = os.path.join(self.root_dir, "app", "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"tts": {"auto_regenerate_bad_clips": True, "auto_regenerate_bad_clip_attempts": 3}}, f)

        self.assertEqual(self.manager._get_auto_regen_retry_attempts(), 3)

    def test_auto_regen_retry_attempts_disables_on_zero_or_invalid(self):
        config_path = os.path.join(self.root_dir, "app", "config.json")

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"tts": {"auto_regenerate_bad_clips": True, "auto_regenerate_bad_clip_attempts": 0}}, f)
        self.assertEqual(self.manager._get_auto_regen_retry_attempts(), 0)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"tts": {"auto_regenerate_bad_clips": True, "auto_regenerate_bad_clip_attempts": "bad"}}, f)
        self.assertEqual(self.manager._get_auto_regen_retry_attempts(), 0)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"tts": {"auto_regenerate_bad_clips": False, "auto_regenerate_bad_clip_attempts": 5}}, f)
        self.assertEqual(self.manager._get_auto_regen_retry_attempts(), 0)

    def test_load_chunks_preserves_corrupt_file_instead_of_regenerating(self):
        chunks_path = os.path.join(self.root_dir, "chunks.json")
        with open(chunks_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        self.assertEqual(self.manager.load_chunks(), [])
        self.assertTrue(os.path.exists(chunks_path))
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "{not valid json")

