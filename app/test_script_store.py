import unittest

from script_store import normalize_script_document


class ScriptStoreTests(unittest.TestCase):
    def test_sanity_cache_round_trips(self):
        loaded = normalize_script_document(
            {
                "entries": [{"speaker": "NARRATOR", "text": "Hello", "instruct": ""}],
                "dictionary": [],
                "sanity_cache": {
                    "phrase_decisions": {
                        "he said softly": {
                            "phrase": "he said softly",
                            "decision": "accepted",
                            "reply": "TRUE",
                            "checked_at": 1,
                        },
                    },
                },
            }
        )
        self.assertIn("sanity_cache", loaded)
        self.assertIn("phrase_decisions", loaded["sanity_cache"])
        self.assertEqual(
            loaded["sanity_cache"]["phrase_decisions"]["he said softly"]["decision"],
            "accepted",
        )

    def test_save_replaces_full_urls_in_entry_text(self):
        loaded = normalize_script_document(
            {
                "entries": [
                    {
                        "speaker": "NARRATOR",
                        "text": "See https://dl.dropboxusercontent.com/s/1owwgy7rfuk8m5g/example.png right now.",
                        "instruct": "",
                    }
                ],
                "dictionary": [],
            }
        )
        self.assertEqual(loaded["entries"][0]["text"], "See [web link] right now.")

    def test_load_replaces_urls_in_existing_document_and_preserves_punctuation(self):
        loaded = normalize_script_document(
            {
                "entries": [
                    {
                        "speaker": "NARRATOR",
                        "text": "Look at https://example.com/test.png, then continue.",
                        "instruct": "",
                    }
                ],
                "dictionary": [],
                "sanity_cache": {"phrase_decisions": {}},
            }
        )
        self.assertEqual(loaded["entries"][0]["text"], "Look at [web link], then continue.")


if __name__ == "__main__":
    unittest.main()
