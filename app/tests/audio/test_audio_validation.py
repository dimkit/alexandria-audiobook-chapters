import unittest

from audio_validation import validate_audio_clip


class AudioValidationTests(unittest.TestCase):
    def test_short_audio_one_word_is_allowed(self):
        result = validate_audio_clip(
            text="No",
            actual_duration_sec=0.08,
            file_size_bytes=1024,
        )
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.error)
        self.assertEqual(result.min_duration_sec, 0.0)

    def test_short_audio_two_words_is_allowed(self):
        result = validate_audio_clip(
            text="No thanks",
            actual_duration_sec=0.08,
            file_size_bytes=1024,
        )
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.error)
        self.assertEqual(result.min_duration_sec, 0.0)

    def test_short_audio_three_words_still_fails(self):
        result = validate_audio_clip(
            text="No no no",
            actual_duration_sec=0.08,
            file_size_bytes=1024,
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Audio is too short", result.error or "")
        self.assertGreater(result.min_duration_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
