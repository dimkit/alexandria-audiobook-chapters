import json
import os
import tempfile
import unittest

from project import ProjectManager
from script_provider import open_project_script_store
from script_repair import (
    _candidate_repair_improves_sanity,
    _pick_next_target,
    _tokenize_with_positions,
    repair_chapter_heading_entries,
    repair_chapter_headings_only,
)


class ScriptRepairTests(unittest.TestCase):
    def test_candidate_repair_requires_monotonic_sanity_improvement(self):
        current = {
            "invalid_section_count": 5,
            "invalid_chunk_count": 7,
            "missing_words": 12,
            "inserted_words": 3,
        }
        improved = {
            "invalid_section_count": 4,
            "invalid_chunk_count": 7,
            "missing_words": 10,
            "inserted_words": 3,
        }
        worsened = {
            "invalid_section_count": 6,
            "invalid_chunk_count": 7,
            "missing_words": 10,
            "inserted_words": 3,
        }

        self.assertTrue(_candidate_repair_improves_sanity(current, improved))
        self.assertFalse(_candidate_repair_improves_sanity(current, worsened))

    def test_candidate_repair_allows_small_inserted_boundary_shift_when_missing_drops(self):
        current = {
            "invalid_section_count": 123,
            "invalid_chunk_count": 62,
            "missing_words": 518,
            "inserted_words": 103,
        }
        candidate = {
            "invalid_section_count": 122,
            "invalid_chunk_count": 62,
            "missing_words": 499,
            "inserted_words": 104,
        }

        self.assertTrue(_candidate_repair_improves_sanity(current, candidate))

    def test_pick_next_target_prefers_merged_replacement_chunks(self):
        sanity_result = {
            "chapters": [
                {
                    "source_title": "Chapter One",
                    "script_title": "Chapter One",
                    "invalid_sections": [
                        {
                            "chapter_title": "Chapter One",
                            "source_char_start": 10,
                            "source_char_end": 20,
                            "script_char_start": 10,
                            "script_char_end": 15,
                            "missing_words": 2,
                            "inserted_words": 0,
                        },
                        {
                            "chapter_title": "Chapter One",
                            "source_char_start": 21,
                            "source_char_end": 28,
                            "script_char_start": 16,
                            "script_char_end": 24,
                            "missing_words": 0,
                            "inserted_words": 3,
                        },
                    ],
                    "replacement_chunks": [
                        {
                            "chapter_title": "Chapter One",
                            "source_char_start": 10,
                            "source_char_end": 28,
                            "script_char_start": 10,
                            "script_char_end": 24,
                            "missing_words": 2,
                            "inserted_words": 3,
                        }
                    ],
                }
            ]
        }

        _chapter, target, _signature = _pick_next_target(sanity_result, set())
        self.assertEqual(target["source_char_start"], 10)
        self.assertEqual(target["source_char_end"], 28)
        self.assertEqual(target["missing_words"], 2)
        self.assertEqual(target["inserted_words"], 3)

    def test_tokenizer_preserves_digits_in_chapter_titles(self):
        tokens = _tokenize_with_positions("Chapter 42: August 8 (Part 1)")
        words = [token["word"] for token in tokens]
        self.assertEqual(words, ["chapter", "42", "august", "8", "part", "1"])

    def test_repair_chapter_heading_entries_restores_split_heading_without_swallowing_following_entry(self):
        with tempfile.TemporaryDirectory() as temp_root:
            os.makedirs(os.path.join(temp_root, "app"), exist_ok=True)
            manager = ProjectManager(temp_root)
            manager.script_store.replace_script_document(
                entries=[
                    {"chapter": "Chapter 42: August 8 (Part 1)", "speaker": "NARRATOR", "text": "Chapter", "instruct": "Neutral, clear announcement."},
                    {"chapter": "Chapter 42: August 8 (Part 1)", "speaker": "NARRATOR", "text": "August", "instruct": "Neutral, clear announcement."},
                    {"chapter": "Chapter 42: August 8 (Part 1)", "speaker": "NARRATOR", "text": "Part Author's Notes", "instruct": "Neutral, clear announcement."},
                    {"chapter": "Chapter 42: August 8 (Part 1)", "speaker": "NARRATOR", "text": "The story continues.", "instruct": ""},
                ],
                dictionary=[],
                sanity_cache={"phrase_decisions": {}},
                reason="test_seed_script",
                rebuild_chunks=False,
                wait=True,
            )

            source_document = {
                "chapters": [
                    {
                        "title": "Chapter 42: August 8 (Part 1)",
                        "text": "Chapter 42: August 8 (Part 1)\n\nPart Author's Notes\n\nThe story continues.",
                    }
                ]
            }

            try:
                repaired = repair_chapter_heading_entries(manager.script_store, source_document)
                self.assertEqual(repaired, 1)
                updated = manager.script_store.load_script_document()
                self.assertEqual(updated["entries"][0]["text"], "Chapter 42: August 8 (Part 1)")
                self.assertEqual(updated["entries"][1]["text"], "Part Author's Notes")
                self.assertEqual(updated["entries"][2]["text"], "The story continues.")
            finally:
                manager.shutdown_script_store(flush=True)

    def test_repair_chapter_headings_only_preserves_chunks_when_headings_change(self):
        with tempfile.TemporaryDirectory() as temp_root:
            uploads_dir = os.path.join(temp_root, "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            os.makedirs(os.path.join(temp_root, "app"), exist_ok=True)
            input_path = os.path.join(uploads_dir, "story.txt")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write("ignored")

            with open(os.path.join(temp_root, "state.json"), "w", encoding="utf-8") as f:
                json.dump({"input_file_path": input_path}, f, indent=2, ensure_ascii=False)

            manager = open_project_script_store(temp_root)
            try:
                manager.replace_script_document(
                    entries=[
                        {"chapter": "Chapter 1: May 23", "speaker": "NARRATOR", "text": "Chapter", "instruct": "Neutral, clear announcement."},
                        {"chapter": "Chapter 1: May 23", "speaker": "NARRATOR", "text": "May", "instruct": "Neutral, clear announcement."},
                        {"chapter": "Chapter 1: May 23", "speaker": "NARRATOR", "text": "Dear Journal.", "instruct": ""},
                    ],
                    dictionary=[],
                    sanity_cache={"phrase_decisions": {}},
                    reason="test_seed_script",
                    rebuild_chunks=False,
                    wait=True,
                )
                manager.replace_chunks(
                    [{"id": 0, "uid": "c1", "text": "stale", "speaker": "NARRATOR", "audio_path": "voicelines/example.mp3", "status": "done"}],
                    reason="test_seed_chunks",
                    wait=True,
                )
                manager.stop(flush=True)
                manager = None

                import script_repair

                original_loader = script_repair.load_source_document
                try:
                    script_repair.load_source_document = lambda _path: {
                        "chapters": [
                            {"title": "Chapter 1: May 23", "text": "Chapter 1: May 23\n\nDear Journal."},
                        ]
                    }
                    result = repair_chapter_headings_only(temp_root)
                finally:
                    script_repair.load_source_document = original_loader

                self.assertEqual(result["repaired_headings"], 1)
                self.assertFalse(result["chunks_reset"])
                manager = open_project_script_store(temp_root)
                chunks = manager.load_chunks()
                self.assertEqual([chunk["text"] for chunk in chunks], ["Chapter 1: May 23", "Dear Journal."])
                self.assertTrue(all(not chunk.get("audio_path") for chunk in chunks))
            finally:
                if manager is not None:
                    manager.stop(flush=True)


if __name__ == "__main__":
    unittest.main()
