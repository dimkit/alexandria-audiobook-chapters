import json
import os
import tempfile
import unittest

from project import ProjectManager


class ProofreadNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = self.temp_dir.name
        os.makedirs(os.path.join(self.root_dir, "app"), exist_ok=True)
        with open(os.path.join(self.root_dir, "annotated_script.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": [], "dictionary": []}, f)
        self.manager = ProjectManager(self.root_dir)

    def tearDown(self):
        self.manager.shutdown_script_store(flush=True)
        self.temp_dir.cleanup()

    def test_get_next_proofread_failure_returns_sqlite_row_candidate(self):
        self.manager.save_chunks(
            [
                {
                    "id": 0,
                    "uid": "chunk-pass",
                    "speaker": "Narrator",
                    "text": "This line passed proofreading.",
                    "chapter": "Chapter 1",
                    "status": "done",
                    "audio_path": "voicelines/pass.mp3",
                    "proofread": {"checked": True, "passed": True},
                },
                {
                    "id": 1,
                    "uid": "chunk-fail",
                    "speaker": "Narrator",
                    "text": "This line failed proofreading.",
                    "chapter": "Chapter 2",
                    "status": "done",
                    "audio_path": "voicelines/fail.mp3",
                    "proofread": {"checked": True, "passed": False},
                },
            ]
        )

        result = self.manager.get_next_proofread_failure()

        self.assertEqual(
            result,
            {"uid": "chunk-fail", "chapter": "Chapter 2", "ordinal": 1},
        )

    def test_get_next_proofread_failure_accepts_after_uid_from_resolved_chunk_ref(self):
        self.manager.save_chunks(
            [
                {
                    "id": 0,
                    "uid": "chunk-fail-1",
                    "speaker": "Narrator",
                    "text": "This line failed first.",
                    "chapter": "Chapter 1",
                    "status": "done",
                    "audio_path": "voicelines/fail-1.mp3",
                    "proofread": {"checked": True, "passed": False},
                },
                {
                    "id": 1,
                    "uid": "chunk-fail-2",
                    "speaker": "Narrator",
                    "text": "This line failed second.",
                    "chapter": "Chapter 2",
                    "status": "done",
                    "audio_path": "voicelines/fail-2.mp3",
                    "proofread": {"checked": True, "passed": False},
                },
            ]
        )

        result = self.manager.get_next_proofread_failure(after_uid="chunk-fail-1")

        self.assertEqual(
            result,
            {"uid": "chunk-fail-2", "chapter": "Chapter 2", "ordinal": 1},
        )
