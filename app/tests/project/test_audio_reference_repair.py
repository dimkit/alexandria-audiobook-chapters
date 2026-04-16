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

class StableAudioFilenameTests(unittest.TestCase):
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

    def _write_temp_wav(self, name, duration_seconds=1.5):
        path = os.path.join(self.root_dir, name)
        sample_rate = 24000
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
        sf.write(path, samples, sample_rate)
        return path

    def test_finalize_generated_audio_uses_chunk_uid_in_filename(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "chunk-alpha",
                "speaker": "Narrator",
                "text": "One two three four five six.",
                "instruct": "",
                "status": "generating",
                "audio_path": None,
            }
        ])
        temp_path = self._write_temp_wav("temp_chunk.wav")

        result = self.manager._finalize_generated_audio(
            0,
            "Narrator",
            "One two three four five six.",
            temp_path,
            chunk_uid="chunk-alpha",
        )

        self.assertEqual(result["status"], "done")
        self.assertEqual(result["audio_path"], "voicelines/voiceline_chunk-alpha_narrator.mp3")

    def test_inserted_chunk_generation_does_not_collide_with_shifted_chunk_audio(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "chunk-a",
                "speaker": "Narrator",
                "text": "First line has enough words for validation to pass cleanly.",
                "instruct": "",
                "status": "done",
                "audio_path": None,
            },
            {
                "id": 1,
                "uid": "chunk-b",
                "speaker": "Narrator",
                "text": "Second line also has enough words for validation to pass cleanly.",
                "instruct": "",
                "status": "done",
                "audio_path": None,
            },
        ])

        original_temp = self._write_temp_wav("temp_original.wav")
        original = self.manager._finalize_generated_audio(
            1,
            "Narrator",
            "Second line also has enough words for validation to pass cleanly.",
            original_temp,
            chunk_uid="chunk-b",
        )

        inserted, chunks = self.manager.insert_chunk(0)
        inserted["text"] = "Inserted line also has enough words for validation to pass cleanly."
        self.manager.save_chunks(chunks)

        inserted_temp = self._write_temp_wav("temp_inserted.wav")
        generated = self.manager._finalize_generated_audio(
            1,
            "Narrator",
            "Inserted line also has enough words for validation to pass cleanly.",
            inserted_temp,
            chunk_uid=inserted["uid"],
        )

        self.assertNotEqual(original["audio_path"], generated["audio_path"])
        self.assertIn("chunk-b", original["audio_path"])
        self.assertIn(inserted["uid"], generated["audio_path"])

class InvalidateStaleAudioReferenceTests(unittest.TestCase):
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

    def test_invalidates_noncanonical_duplicate_legacy_audio_references(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "One",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_0001_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "u1",
                "speaker": "Narrator",
                "text": "Two",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_0001_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
            {
                "id": 2,
                "uid": "u2",
                "speaker": "Narrator",
                "text": "Three",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_0003_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
        ])

        result = self.manager.invalidate_stale_audio_references()
        updated = self.manager.load_chunks()

        self.assertEqual(result["invalidated"], 1)
        self.assertEqual(updated[0]["audio_path"], "voicelines/voiceline_0001_narrator.mp3")
        self.assertIsNone(updated[1]["audio_path"])
        self.assertEqual(updated[1]["status"], "pending")
        self.assertEqual(updated[2]["audio_path"], "voicelines/voiceline_0003_narrator.mp3")

    def test_invalidates_duplicate_uid_based_audio_for_nonmatching_chunks(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "chunk-alpha",
                "speaker": "Narrator",
                "text": "One",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_chunk-alpha_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "chunk-beta",
                "speaker": "Narrator",
                "text": "Two",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_chunk-alpha_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
        ])

        result = self.manager.invalidate_stale_audio_references()
        updated = self.manager.load_chunks()

        self.assertEqual(result["invalidated"], 1)
        self.assertEqual(updated[0]["audio_path"], "voicelines/voiceline_chunk-alpha_narrator.mp3")
        self.assertIsNone(updated[1]["audio_path"])

    def test_keeps_unique_legacy_audio_references_even_if_index_has_shifted(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Moved but still valid",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/voiceline_0005_narrator.mp3",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            }
        ])

        result = self.manager.invalidate_stale_audio_references()
        updated = self.manager.load_chunks()

        self.assertEqual(result["invalidated"], 0)
        self.assertEqual(updated[0]["audio_path"], "voicelines/voiceline_0005_narrator.mp3")

class RepairLostAudioLinksTests(unittest.TestCase):
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
        sample_rate = 24000
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
        sf.write(full_path, samples, sample_rate)
        return full_path

    def test_rebuilds_from_exact_transcript_match_anywhere_in_project(self):
        self._write_wav("voicelines/voiceline_0008_narrator.wav", 0.4)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Opening line that should remain unmatched.",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/old_wrong_clip.wav",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "u1",
                "speaker": "Narrator",
                "text": "The recovered line belongs here and should be restored.",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/another_wrong_clip.wav",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "The recovered line belongs here and should be restored.",
                    "normalized_text": self.manager._normalize_asr_text("The recovered line belongs here and should be restored."),
                }
            }
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {
                "is_valid": False,
                "error": "Skipped duration validation in test.",
            }

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["relinked"], 1)
            self.assertEqual(result["asr_relinked"], 1)
            self.assertIsNone(repaired[0]["audio_path"])
            self.assertEqual(repaired[1]["audio_path"], "voicelines/voiceline_u1_narrator.wav")
            self.assertTrue(repaired[1]["audio_validation"]["repair_exact_transcript_match"])
            self.assertFalse(os.path.exists(os.path.join(self.root_dir, "voicelines/voiceline_0008_narrator.wav")))
            self.assertTrue(os.path.exists(os.path.join(self.root_dir, "voicelines/voiceline_u1_narrator.wav")))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_discards_clip_when_exact_transcript_matches_multiple_same_speaker_chunks(self):
        self._write_wav("voicelines/voiceline_0001_narrator.wav", 0.4)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Repeated line that appears twice.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "u1",
                "speaker": "Narrator",
                "text": "Repeated line that appears twice.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Repeated line that appears twice.",
                    "normalized_text": self.manager._normalize_asr_text("Repeated line that appears twice."),
                }
            }

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["relinked"], 0)
            self.assertEqual(result["invalid_candidates"], 1)
            self.assertIsNone(repaired[0]["audio_path"])
            self.assertIsNone(repaired[1]["audio_path"])
            self.assertTrue(os.path.exists(os.path.join(self.root_dir, "voicelines/discarded/voiceline_0001_narrator.wav")))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_discards_unmatched_clip_and_skips_discarded_on_future_runs(self):
        self._write_wav("voicelines/voiceline_0001_narrator.wav", 0.4)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Only line in project.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Completely different transcript.",
                    "normalized_text": self.manager._normalize_asr_text("Completely different transcript."),
                }
            }

            first = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()
            second = self.manager.repair_lost_audio_links(use_asr=True)

            self.assertEqual(first["unmatched_files"], 1)
            self.assertEqual(second["total_candidates"], 0)
            self.assertIsNone(repaired[0]["audio_path"])
            self.assertTrue(os.path.exists(os.path.join(self.root_dir, "voicelines/discarded/voiceline_0001_narrator.wav")))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_lost_audio_repair_uses_alias_tolerant_speaker_match(self):
        self._write_wav("voicelines/voiceline_0001_narrator.wav", 0.4)
        self.manager._save_voice_config({
            "Guide": {"alias": "Narrator"},
            "Narrator": {},
        })
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Guide",
                "text": "Alias-tolerant match should be restored.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Alias-tolerant match should be restored.",
                    "normalized_text": self.manager._normalize_asr_text("Alias-tolerant match should be restored."),
                }
            }
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["relinked"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/voiceline_u0_guide.wav")
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_discards_later_duplicate_clip_for_same_unique_chunk(self):
        first = self._write_wav("voicelines/voiceline_0001_narrator.wav", 0.4)
        second = self._write_wav("voicelines/voiceline_0002_narrator.wav", 0.4)
        os.utime(first, (100, 100))
        os.utime(second, (200, 200))
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Only one exact destination exists.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                path: {
                    "text": "Only one exact destination exists.",
                    "normalized_text": self.manager._normalize_asr_text("Only one exact destination exists."),
                }
                for path in paths
            }

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["relinked"], 1)
            self.assertEqual(result["duplicate_matches"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/voiceline_u0_narrator.wav")
            self.assertTrue(os.path.exists(os.path.join(self.root_dir, "voicelines/discarded/voiceline_0001_narrator.wav")))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_repair_lost_audio_links_regrades_discarded_clips_when_main_pool_empty(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        self._write_wav("voicelines/discarded/voiceline_0001_narrator.wav", 0.4)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"proofread": {"certainty_threshold": 0.75}}, f)

        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Recovered from discarded clips.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_metrics = self.manager._proofread_similarity_metrics
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Recovered from discarded clips with a small deviation.",
                    "normalized_text": self.manager._normalize_asr_text("Recovered from discarded clips with a small deviation."),
                }
            }
            self.manager._proofread_similarity_metrics = lambda expected, transcript: {"score": 0.82}
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["discarded_retry_relinked"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/voiceline_u0_narrator.wav")
            self.assertTrue(repaired[0]["audio_validation"]["repair_certainty_match"])
            self.assertEqual(repaired[0]["audio_validation"]["repair_certainty_threshold"], 0.75)
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._proofread_similarity_metrics = original_metrics
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_repair_lost_audio_links_keeps_discarded_clip_when_score_is_below_certainty(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        self._write_wav("voicelines/discarded/voiceline_0001_narrator.wav", 0.4)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"proofread": {"certainty_threshold": 0.9}}, f)

        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Should remain discarded.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_metrics = self.manager._proofread_similarity_metrics
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Should remain discarded after regrading.",
                    "normalized_text": self.manager._normalize_asr_text("Should remain discarded after regrading."),
                }
            }
            self.manager._proofread_similarity_metrics = lambda expected, transcript: {"score": 0.6}

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["discarded_retry_relinked"], 0)
            self.assertIsNone(repaired[0]["audio_path"])
            self.assertTrue(os.path.exists(os.path.join(self.root_dir, "voicelines/discarded/voiceline_0001_narrator.wav")))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._proofread_similarity_metrics = original_metrics

    def test_repair_lost_audio_links_rejected_only_does_not_reset_existing_assignments(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        self._write_wav("voicelines/active.wav", 0.4)
        self._write_wav("voicelines/discarded/voiceline_0002_narrator.wav", 0.4)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"proofread": {"certainty_threshold": 0.7}}, f)

        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Already assigned clip.",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/active.wav",
                "audio_validation": {"is_valid": True},
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "u1",
                "speaker": "Narrator",
                "text": "Recover from rejected only.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_metrics = self.manager._proofread_similarity_metrics
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "Recover from rejected only.",
                    "normalized_text": self.manager._normalize_asr_text("Recover from rejected only."),
                }
            }
            self.manager._proofread_similarity_metrics = lambda expected, transcript: {"score": 0.8}
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            result = self.manager.repair_lost_audio_links(use_asr=True, rejected_only=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["discarded_retry_relinked"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/active.wav")
            self.assertEqual(repaired[1]["audio_path"], "voicelines/voiceline_u1_narrator.wav")
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._proofread_similarity_metrics = original_metrics
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_best_discarded_repair_match_can_use_rare_word_drop(self):
        chunks = [
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Common words aurora lantern linger softly tonight.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
            {
                "id": 1,
                "uid": "u1",
                "speaker": "Narrator",
                "text": "Common words gather gently around the fire tonight.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ]
        dictionary_entries = []
        voice_config = {}
        match_cache = self.manager._build_repair_match_cache(chunks, dictionary_entries, voice_config)

        original_metrics = self.manager._proofread_similarity_metrics
        try:
            def fake_metrics(expected, transcript):
                normalized_expected = self.manager._normalize_asr_text(expected)
                normalized_transcript = self.manager._normalize_asr_text(transcript)
                if (
                    normalized_expected == "common words linger softly tonight"
                    and normalized_transcript == "common words linger softly tonight"
                ):
                    return {"score": 1.0}
                return {"score": 0.55}

            self.manager._proofread_similarity_metrics = fake_metrics
            match = self.manager._best_discarded_repair_match(
                "narrator",
                "Common words aurora lantern linger softly tonight.",
                set(),
                0.9,
                match_cache,
            )

            self.assertIsNotNone(match)
            self.assertEqual(match["index"], 0)
            self.assertEqual(match["score"], 1.0)
            self.assertTrue(match["metrics"]["reduced_transcript_match"])
            self.assertEqual(match["metrics"]["dropped_low_frequency_words"], ["aurora", "lantern"])
        finally:
            self.manager._proofread_similarity_metrics = original_metrics

    def test_repair_lost_audio_links_batches_rejected_checkpoint_writes(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"proofread": {"certainty_threshold": 0.75}}, f)

        discarded_paths = []
        chunks = []
        for i in range(30):
            rel = f"voicelines/discarded/voiceline_{i+1:04d}_narrator.wav"
            self._write_wav(rel, 0.4)
            discarded_paths.append(rel)
            chunks.append({
                "id": i,
                "uid": f"u{i}",
                "speaker": "Narrator",
                "text": f"Recovered rejected line {i}.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            })
        self.manager.save_chunks(chunks)

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_validate = self.manager._validate_audio_path_for_chunk
        original_atomic_write = self.manager._atomic_json_write
        write_calls = []
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                path: {
                    "text": f"Recovered rejected line {int(os.path.basename(path).split('_')[1]) - 1}.",
                    "normalized_text": self.manager._normalize_asr_text(
                        f"Recovered rejected line {int(os.path.basename(path).split('_')[1]) - 1}."
                    ),
                }
                for path in paths
            }
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            def tracked_atomic_write(payload, destination_path):
                if destination_path == self.manager.chunks_path:
                    write_calls.append(destination_path)
                return original_atomic_write(payload, destination_path)

            self.manager._atomic_json_write = tracked_atomic_write

            result = self.manager.repair_lost_audio_links(use_asr=True, rejected_only=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["discarded_retry_relinked"], 30)
            self.assertTrue(all(chunk.get("audio_path") for chunk in repaired))
            self.assertEqual(len(write_calls), 2)
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._validate_audio_path_for_chunk = original_validate
            self.manager._atomic_json_write = original_atomic_write

    def test_repair_commit_copies_cached_transcription_to_renamed_uid_path(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        self._write_wav("voicelines/discarded/voiceline_0001_narrator.wav", 0.4)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Recovered line.",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        self.manager._store_cached_transcription(
            "voicelines/discarded/voiceline_0001_narrator.wav",
            {
                "text": "Recovered line.",
                "normalized_text": self.manager._normalize_asr_text("Recovered line."),
            },
        )

        chunks = self.manager.load_chunks()
        committed = self.manager._commit_repaired_chunk_locked(
            chunks,
            0,
            "voicelines/discarded/voiceline_0001_narrator.wav",
            {"is_valid": True},
        )

        cached = self.manager._lookup_cached_transcription(committed)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["text"], "Recovered line.")

    def test_repair_lost_audio_links_exact_match_ignores_punctuation(self):
        self._write_wav("voicelines/voiceline_0001_narrator.wav", 0.4)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "What’s a cutie mark?!",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "What's a cutie mark",
                    "normalized_text": self.manager._normalize_asr_text("What's a cutie mark"),
                }
            }
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            result = self.manager.repair_lost_audio_links(use_asr=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["relinked"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/voiceline_u0_narrator.wav")
            self.assertTrue(repaired[0]["audio_validation"]["repair_exact_transcript_match"])
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_repair_lost_audio_links_discarded_retry_ignores_punctuation(self):
        os.makedirs(os.path.join(self.root_dir, "voicelines", "discarded"), exist_ok=True)
        self._write_wav("voicelines/discarded/voiceline_0001_narrator.wav", 0.4)
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "app", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"proofread": {"certainty_threshold": 0.75}}, f)

        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "What’s a cutie mark?!",
                "instruct": "",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_validate = self.manager._validate_audio_path_for_chunk
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                paths[0]: {
                    "text": "What's a cutie mark",
                    "normalized_text": self.manager._normalize_asr_text("What's a cutie mark"),
                }
            }
            self.manager._validate_audio_path_for_chunk = lambda chunk, path, dictionary_entries: {"is_valid": True}

            result = self.manager.repair_lost_audio_links(use_asr=True, rejected_only=True)
            repaired = self.manager.load_chunks()

            self.assertEqual(result["discarded_retry_relinked"], 1)
            self.assertEqual(repaired[0]["audio_path"], "voicelines/voiceline_u0_narrator.wav")
            self.assertTrue(repaired[0]["audio_validation"]["repair_certainty_match"])
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager._validate_audio_path_for_chunk = original_validate

    def test_proofread_uses_alias_tolerant_speaker_match(self):
        uid = "0123456789abcdef0123456789abcdef"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 2.0)
        self.manager._save_voice_config({
            "Guide": {
                "alias": "Narrator",
            },
            "Narrator": {},
        })
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Guide",
                "text": "The stars aligned in perfect silence.",
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            self.manager.transcribe_audio_path = lambda relative_path: {
                "text": "The stars aligned in perfect silence.",
                "normalized_text": self.manager._normalize_asr_text("The stars aligned in perfect silence."),
            }
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            chunks = self.manager.load_chunks()
            proofread = chunks[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertTrue(proofread["speaker_match"])
            self.assertGreaterEqual(proofread["score"], 0.9)
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_proofread_similarity_ignores_punctuation(self):
        metrics = self.manager._proofread_similarity_metrics(
            "Wait... what?! Are you sure: 42?",
            "Wait what are you sure 42",
        )
        self.assertEqual(metrics["score"], 1.0)

    def test_proofread_similarity_accepts_common_abbreviation_expansions(self):
        metrics = self.manager._proofread_similarity_metrics(
            "Dr Smith arrived just in time.",
            "Doctor Smith arrived just in time",
        )
        self.assertEqual(metrics["score"], 1.0)
        self.assertTrue(metrics.get("abbreviation_expanded_match"))

    def test_proofread_reuses_repair_cached_transcript_from_audio_validation(self):
        uid = "44444444444444444444444444444444"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 2.0)
        text = "What’s a cutie mark?!"
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": text,
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": {
                    "is_valid": True,
                    "transcript_text": "What's a cutie mark",
                    "normalized_transcript": self.manager._normalize_asr_text("What's a cutie mark"),
                },
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            def should_not_run(paths, progress_callback=None):
                raise AssertionError("Proofread should reuse repair-cached transcript from audio_validation")

            self.manager.transcribe_audio_paths_bulk = should_not_run
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            chunks = self.manager.load_chunks()
            proofread = chunks[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertEqual(proofread["transcript_text"], "What's a cutie mark")
            self.assertTrue(proofread["passed"])
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_proofread_reuses_cached_audio_duration_from_audio_validation(self):
        uid = "45454545454545454545454545454545"
        audio_path = f"voicelines/voiceline_{uid}_narrator.wav"
        self._write_wav(audio_path, 2.0)
        text = "Cached duration should be reused."
        full_audio_path = os.path.join(self.root_dir, audio_path)
        file_size = os.path.getsize(full_audio_path)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": text,
                "instruct": "",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": {
                    "is_valid": True,
                    "actual_duration_sec": 2.0,
                    "file_size_bytes": file_size,
                    "transcript_text": text,
                    "normalized_transcript": self.manager._normalize_asr_text(text),
                },
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        import project as project_module
        original_duration_fn = project_module.get_audio_duration_seconds
        try:
            def should_not_run(_path):
                raise AssertionError("Proofread should reuse cached audio duration from audio_validation")

            project_module.get_audio_duration_seconds = should_not_run
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            proofread = self.manager.load_chunks()[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertEqual(proofread["actual_duration_sec"], 2.0)
            self.assertTrue(proofread["passed"])
        finally:
            project_module.get_audio_duration_seconds = original_duration_fn

    def test_proofread_batches_chunk_writes(self):
        uids = [
            "11111111111111111111111111111111",
            "22222222222222222222222222222222",
            "33333333333333333333333333333333",
        ]
        for uid in uids:
            self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 2.0)

        self.manager.save_chunks([
            {
                "id": i,
                "uid": uid,
                "speaker": "Narrator",
                "text": f"Proofread line {i}.",
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            }
            for i, uid in enumerate(uids)
        ])

        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        original_patch_chunks_if = self.manager.patch_chunks_if
        patch_calls = []
        try:
            self.manager.transcribe_audio_paths_bulk = lambda paths, progress_callback=None: {
                path: {
                    "text": f"Proofread line {index}.",
                    "normalized_text": self.manager._normalize_asr_text(f"Proofread line {index}."),
                }
                for index, path in enumerate(paths)
            }

            def tracked_patch_chunks_if(updates, reason="patch_chunks_if"):
                patch_calls.append((reason, len(updates or [])))
                return original_patch_chunks_if(updates, reason=reason)

            self.manager.patch_chunks_if = tracked_patch_chunks_if

            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            reloaded = self.manager.load_chunks()

            self.assertEqual(result["processed"], 3)
            self.assertEqual(len(patch_calls), 1)
            self.assertEqual(patch_calls[0][0], "proofread_batch")
            self.assertEqual(patch_calls[0][1], 3)
            self.assertTrue(all(chunk.get("proofread", {}).get("checked") for chunk in reloaded))
        finally:
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk
            self.manager.patch_chunks_if = original_patch_chunks_if

    def test_proofread_auto_fails_large_duration_mismatch_without_asr(self):
        uid = "fedcba9876543210fedcba9876543210"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 3.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": (
                    "This is a much longer line that should auto fail due to duration mismatch without transcription. "
                    "It keeps going well beyond a normal clip length so the duration delta is obviously extreme. "
                    "That ensures the proofread pass still short circuits before ASR even with the wider tolerance. "
                    "Additional filler words push the expected speaking time high enough that the new long clip gate "
                    "still clearly identifies this as an impossible duration match without needing Whisper at all."
                ),
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            def should_not_run(relative_path):
                raise AssertionError("ASR should not run for obvious duration outliers")
            self.manager.transcribe_audio_path = should_not_run
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=1.0)
            chunks = self.manager.load_chunks()
            proofread = chunks[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["auto_failed"], 1)
            self.assertEqual(proofread["score"], 0.0)
            self.assertEqual(proofread["auto_failed_reason"], "duration_outlier")
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_proofread_long_chunk_uses_more_tolerant_duration_gate(self):
        uid = "abcdefabcdefabcdefabcdefabcdefab"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 0.25)
        long_text = (
            "This is a deliberately long narration block that goes well past twenty five words so that proofread should "
            "use the wider duration tolerance before deciding whether to skip ASR and auto fail the line outright."
        )
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": long_text,
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            self.manager.transcribe_audio_path = lambda relative_path: {
                "text": long_text,
                "normalized_text": self.manager._normalize_asr_text(long_text),
            }
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            chunks = self.manager.load_chunks()
            proofread = chunks[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["auto_failed"], 0)
            self.assertIsNone(proofread["auto_failed_reason"])
            self.assertTrue(proofread["passed"])
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_proofread_short_audio_always_runs_asr(self):
        uid = "1234567890abcdef1234567890abcdef"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 1.5)
        text = (
            "This transcript is intentionally much longer than the short clip duration so the duration gate would "
            "normally auto fail it if the short-audio ASR bypass were not in place."
        )
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": text,
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            self.manager.transcribe_audio_path = lambda relative_path: {
                "text": text,
                "normalized_text": self.manager._normalize_asr_text(text),
            }
            result = self.manager.proofread_chunks(chapter="Prologue", threshold=0.9)
            chunks = self.manager.load_chunks()
            proofread = chunks[0]["proofread"]

            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["auto_failed"], 0)
            self.assertIsNone(proofread["auto_failed_reason"])
            self.assertTrue(proofread["passed"])
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_compare_proofread_clip_forces_transcript_on_duration_outlier(self):
        uid = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab"
        self._write_wav(f"voicelines/voiceline_{uid}_narrator.wav", 3.0)
        text = (
            "This line is intentionally long enough that the normal proofread duration gate would have rejected it "
            "without generating a transcript first."
        )
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": text,
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_narrator.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            self.manager.transcribe_audio_path = lambda relative_path: {
                "text": text,
                "normalized_text": self.manager._normalize_asr_text(text),
            }
            updated = self.manager.compare_proofread_clip(uid, threshold=0.9)
            reloaded = self.manager.load_chunks()
            proofread = reloaded[0]["proofread"]

            self.assertIsNotNone(updated)
            self.assertTrue(proofread["forced_compare"])
            self.assertEqual(proofread["transcript_text"], text)
            self.assertIsNone(proofread["auto_failed_reason"])
            self.assertTrue(proofread["passed"])
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_compare_proofread_clip_transcribes_even_on_speaker_mismatch(self):
        uid = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self._write_wav(f"voicelines/voiceline_{uid}_other.wav", 1.5)
        text = "Speaker mismatch but still compare."
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": uid,
                "speaker": "Narrator",
                "text": text,
                "instruct": "",
                "status": "done",
                "audio_path": f"voicelines/voiceline_{uid}_other.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "chapter": "Prologue",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        try:
            self.manager.transcribe_audio_path = lambda relative_path: {
                "text": text,
                "normalized_text": self.manager._normalize_asr_text(text),
            }
            self.manager.compare_proofread_clip(uid, threshold=0.9)
            reloaded = self.manager.load_chunks()
            proofread = reloaded[0]["proofread"]

            self.assertTrue(proofread["forced_compare"])
            self.assertFalse(proofread["speaker_match"])
            self.assertEqual(proofread["transcript_text"], text)
            self.assertFalse(proofread["passed"])
            self.assertEqual(proofread["error"], "Audio filename speaker does not match the chunk speaker.")
        finally:
            self.manager.transcribe_audio_path = original_transcribe

    def test_update_chunk_clears_proofread_state(self):
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "u0",
                "speaker": "Narrator",
                "text": "Original line.",
                "instruct": "",
                "status": "done",
                "audio_path": "voicelines/example.wav",
                "audio_validation": None,
                "auto_regen_count": 0,
                "proofread": {
                    "checked": True,
                    "score": 1.0,
                },
            },
        ])

        updated = self.manager.update_chunk("u0", {"text": "Updated line."})
        self.assertIsNone(updated["audio_path"])
        self.assertIsNone(updated["audio_validation"])
        self.assertEqual(updated["status"], "pending")
        self.assertNotIn("proofread", updated)
        reloaded = self.manager.load_chunks()
        self.assertIsNone(reloaded[0]["audio_path"])
        self.assertIsNone(reloaded[0]["audio_validation"])
        self.assertEqual(reloaded[0]["status"], "pending")
        self.assertNotIn("proofread", reloaded[0])

    def test_prepare_chunk_for_regeneration_removes_old_audio_and_clears_state(self):
        audio_path = "voicelines/voiceline_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "speaker": "Narrator",
                "text": "Regenerate this line.",
                "instruct": "",
                "status": "error",
                "audio_path": audio_path,
                "audio_validation": {"error": "bad clip"},
                "auto_regen_count": 2,
                "proofread": {"checked": True, "score": 0.1},
            },
        ])

        prepared = self.manager.prepare_chunk_for_regeneration("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertIsNotNone(prepared)
        self.assertFalse(os.path.exists(os.path.join(self.root_dir, audio_path)))

        reloaded = self.manager.load_chunks()
        self.assertIsNone(reloaded[0]["audio_path"])
        self.assertIsNone(reloaded[0]["audio_validation"])
        self.assertEqual(reloaded[0]["status"], "pending")
        self.assertNotIn("proofread", reloaded[0])

    def test_clear_proofread_failures_clears_only_failed_graded_audio(self):
        failed_audio = "voicelines/voiceline_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb_narrator.wav"
        passed_audio = "voicelines/voiceline_cccccccccccccccccccccccccccccccc_narrator.wav"
        ungraded_audio = "voicelines/voiceline_dddddddddddddddddddddddddddddddd_narrator.wav"
        self._write_wav(failed_audio, 1.0)
        self._write_wav(passed_audio, 1.0)
        self._write_wav(ungraded_audio, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "speaker": "Narrator",
                "text": "Failed clip.",
                "status": "done",
                "audio_path": failed_audio,
                "audio_validation": None,
                "proofread": {"checked": True, "score": 0.2, "passed": False},
                "chapter": "Chapter One",
            },
            {
                "id": 1,
                "uid": "cccccccccccccccccccccccccccccccc",
                "speaker": "Narrator",
                "text": "Passed clip.",
                "status": "done",
                "audio_path": passed_audio,
                "audio_validation": None,
                "proofread": {"checked": True, "score": 1.0, "passed": True},
                "chapter": "Chapter One",
            },
            {
                "id": 2,
                "uid": "dddddddddddddddddddddddddddddddd",
                "speaker": "Narrator",
                "text": "Ungraded clip.",
                "status": "done",
                "audio_path": ungraded_audio,
                "audio_validation": None,
                "chapter": "Chapter One",
            },
        ])

        result = self.manager.clear_proofread_failures(chapter="Chapter One", threshold=1.0)
        reloaded = self.manager.load_chunks()

        self.assertEqual(result["cleared"], 1)
        self.assertEqual(result["ungraded_with_audio"], 1)
        self.assertFalse(os.path.exists(os.path.join(self.root_dir, failed_audio)))
        self.assertTrue(os.path.exists(os.path.join(self.root_dir, passed_audio)))
        self.assertTrue(os.path.exists(os.path.join(self.root_dir, ungraded_audio)))
        self.assertIsNone(reloaded[0]["audio_path"])
        self.assertNotIn("proofread", reloaded[0])
        self.assertEqual(reloaded[1]["audio_path"], passed_audio)
        self.assertEqual(reloaded[2]["audio_path"], ungraded_audio)

    def test_manually_validate_proofread_clip_marks_clip_safe(self):
        audio_path = "voicelines/voiceline_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "speaker": "Narrator",
                "text": "Clip to validate manually.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {"checked": True, "score": 0.2, "passed": False, "error": "Transcript confidence below threshold."},
                "chapter": "Chapter One",
            },
        ])

        updated = self.manager.manually_validate_proofread_clip("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", threshold=1.0)
        reloaded = self.manager.load_chunks()

        self.assertIsNotNone(updated)
        self.assertTrue(reloaded[0]["proofread"]["checked"])
        self.assertTrue(reloaded[0]["proofread"]["passed"])
        self.assertEqual(reloaded[0]["proofread"]["score"], 1.0)
        self.assertTrue(reloaded[0]["proofread"]["manual_validated"])
        self.assertFalse(reloaded[0]["proofread"]["manual_failed"])
        self.assertIsNone(reloaded[0]["proofread"]["error"])

    def test_manually_validate_proofread_clip_toggles_validated_clip_to_manual_failure(self):
        audio_path = "voicelines/voiceline_abababababababababababababababab_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "abababababababababababababababab",
                "speaker": "Narrator",
                "text": "Clip to reject manually.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": True,
                    "score": 1.0,
                    "passed": True,
                    "manual_validated": True,
                    "audio_path": audio_path,
                    "validated_at": 123.0,
                },
                "chapter": "Chapter One",
            },
        ])

        updated = self.manager.manually_validate_proofread_clip("abababababababababababababababab", threshold=1.0)
        reloaded = self.manager.load_chunks()

        self.assertIsNotNone(updated)
        self.assertTrue(reloaded[0]["proofread"]["checked"])
        self.assertFalse(reloaded[0]["proofread"]["passed"])
        self.assertEqual(reloaded[0]["proofread"]["score"], 0.0)
        self.assertFalse(reloaded[0]["proofread"]["manual_validated"])
        self.assertTrue(reloaded[0]["proofread"]["manual_failed"])
        self.assertEqual(reloaded[0]["proofread"]["error"], "Manually marked as failed by user.")

    def test_clear_proofread_failures_keeps_manually_validated_clip(self):
        audio_path = "voicelines/voiceline_ffffffffffffffffffffffffffffffff_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "ffffffffffffffffffffffffffffffff",
                "speaker": "Narrator",
                "text": "Clip kept by manual validation.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {"checked": True, "score": 1.0, "passed": True, "manual_validated": True},
                "chapter": "Chapter One",
            },
        ])

        result = self.manager.clear_proofread_failures(chapter="Chapter One", threshold=1.0)
        reloaded = self.manager.load_chunks()

        self.assertEqual(result["cleared"], 0)
        self.assertTrue(os.path.exists(os.path.join(self.root_dir, audio_path)))
        self.assertEqual(reloaded[0]["audio_path"], audio_path)
        self.assertTrue(reloaded[0]["proofread"]["manual_validated"])

    def test_discard_proofread_selection_preserves_transcript_for_same_audio(self):
        audio_path = "voicelines/voiceline_11111111111111111111111111111111_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "11111111111111111111111111111111",
                "speaker": "Narrator",
                "text": "Clip with cached transcript.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": True,
                    "score": 0.6,
                    "passed": False,
                    "audio_path": audio_path,
                    "transcript_text": "Clip with cached transcript.",
                    "normalized_transcript": "clip with cached transcript",
                },
                "chapter": "Chapter One",
            },
        ])

        result = self.manager.discard_proofread_selection(chapter="Chapter One")
        reloaded = self.manager.load_chunks()
        proofread = reloaded[0]["proofread"]

        self.assertEqual(result["discarded"], 1)
        self.assertEqual(result["preserved_transcripts"], 1)
        self.assertFalse(proofread["checked"])
        self.assertEqual(proofread["audio_path"], audio_path)
        self.assertEqual(proofread["transcript_text"], "Clip with cached transcript.")
        self.assertNotIn("score", proofread)

    def test_discard_proofread_selection_clears_state_without_transcript(self):
        audio_path = "voicelines/voiceline_22222222222222222222222222222222_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "22222222222222222222222222222222",
                "speaker": "Narrator",
                "text": "Clip without transcript.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": True,
                    "score": 0.0,
                    "passed": False,
                    "audio_path": audio_path,
                },
                "chapter": "Chapter One",
            },
        ])

        result = self.manager.discard_proofread_selection(chapter="Chapter One")
        reloaded = self.manager.load_chunks()

        self.assertEqual(result["discarded"], 1)
        self.assertEqual(result["cleared_transcripts"], 1)
        self.assertNotIn("proofread", reloaded[0])

    def test_proofread_reuses_cached_transcript_after_discard(self):
        audio_path = "voicelines/voiceline_33333333333333333333333333333333_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "33333333333333333333333333333333",
                "speaker": "Narrator",
                "text": "Cached transcript should be reused.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": False,
                    "audio_path": audio_path,
                    "transcript_text": "Cached transcript should be reused.",
                    "normalized_transcript": "cached transcript should be reused",
                },
                "chapter": "Chapter One",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            def should_not_run(*args, **kwargs):
                raise AssertionError("ASR should not run when cached transcript matches current audio")
            self.manager.transcribe_audio_path = should_not_run
            self.manager.transcribe_audio_paths_bulk = should_not_run

            result = self.manager.proofread_chunks(chapter="Chapter One", threshold=1.0)
            reloaded = self.manager.load_chunks()

            self.assertEqual(result["processed"], 1)
            self.assertTrue(reloaded[0]["proofread"]["checked"])
            self.assertTrue(reloaded[0]["proofread"]["passed"])
            self.assertEqual(reloaded[0]["proofread"]["transcript_text"], "Cached transcript should be reused.")
        finally:
            self.manager.transcribe_audio_path = original_transcribe
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_proofread_auto_resets_scope_when_everything_is_already_scored(self):
        audio_path = "voicelines/voiceline_44444444444444444444444444444444_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "44444444444444444444444444444444",
                "speaker": "Narrator",
                "text": "Rerun this graded line.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": True,
                    "score": 0.4,
                    "passed": False,
                    "audio_path": audio_path,
                    "transcript_text": "Rerun this graded line.",
                    "normalized_transcript": "rerun this graded line",
                },
                "chapter": "Chapter One",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            def should_not_run(*args, **kwargs):
                raise AssertionError("ASR should not rerun when transcript cache is preserved")
            self.manager.transcribe_audio_path = should_not_run
            self.manager.transcribe_audio_paths_bulk = should_not_run

            result = self.manager.proofread_chunks(chapter="Chapter One", threshold=1.0)
            reloaded = self.manager.load_chunks()

            self.assertEqual(result["auto_reset_discarded"], 1)
            self.assertEqual(result["processed"], 1)
            self.assertTrue(reloaded[0]["proofread"]["checked"])
            self.assertTrue(reloaded[0]["proofread"]["passed"])
            self.assertEqual(reloaded[0]["proofread"]["transcript_text"], "Rerun this graded line.")
        finally:
            self.manager.transcribe_audio_path = original_transcribe
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

    def test_proofread_auto_reset_preserves_manual_validation(self):
        audio_path = "voicelines/voiceline_55555555555555555555555555555555_narrator.wav"
        self._write_wav(audio_path, 1.0)
        self.manager.save_chunks([
            {
                "id": 0,
                "uid": "55555555555555555555555555555555",
                "speaker": "Narrator",
                "text": "Keep this manual validation.",
                "status": "done",
                "audio_path": audio_path,
                "audio_validation": None,
                "proofread": {
                    "checked": True,
                    "score": 1.0,
                    "passed": True,
                    "audio_path": audio_path,
                    "manual_validated": True,
                    "validated_at": 123.0,
                },
                "chapter": "Chapter One",
            },
        ])

        original_transcribe = self.manager.transcribe_audio_path
        original_transcribe_bulk = self.manager.transcribe_audio_paths_bulk
        try:
            def should_not_run(*args, **kwargs):
                raise AssertionError("Manually validated unchanged audio should remain skipped")
            self.manager.transcribe_audio_path = should_not_run
            self.manager.transcribe_audio_paths_bulk = should_not_run

            result = self.manager.proofread_chunks(chapter="Chapter One", threshold=1.0)
            reloaded = self.manager.load_chunks()

            self.assertEqual(result["auto_reset_discarded"], 0)
            self.assertEqual(result["processed"], 0)
            self.assertTrue(reloaded[0]["proofread"]["manual_validated"])
            self.assertTrue(reloaded[0]["proofread"]["checked"])
        finally:
            self.manager.transcribe_audio_path = original_transcribe
            self.manager.transcribe_audio_paths_bulk = original_transcribe_bulk

if __name__ == "__main__":
    unittest.main()

