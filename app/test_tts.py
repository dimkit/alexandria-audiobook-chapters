import unittest
from unittest import mock
import tempfile
import os
import base64

from tts import TTSEngine


class NormalizeExternalUrlTests(unittest.TestCase):
    def test_defaults_empty_value(self):
        self.assertEqual(
            TTSEngine._normalize_external_url(""),
            "http://127.0.0.1:7860",
        )

    def test_preserves_http_url(self):
        self.assertEqual(
            TTSEngine._normalize_external_url("http://127.0.0.1:7860/"),
            "http://127.0.0.1:7860",
        )

    def test_adds_http_to_bare_host_port(self):
        self.assertEqual(
            TTSEngine._normalize_external_url("localhost:42003"),
            "http://localhost:42003",
        )

    def test_rejects_unsupported_scheme(self):
        with self.assertRaises(ValueError):
            TTSEngine._normalize_external_url("ftp://localhost:42003")

    @mock.patch("tts.httpx.get")
    def test_external_url_candidates_include_redirect_target(self, mock_get):
        mock_get.return_value.url = "http://localhost:42003/gradio"
        candidates = TTSEngine._external_url_candidates("localhost:42003")
        self.assertEqual(candidates[0], "http://localhost:42003")
        self.assertIn("http://localhost:42003/gradio", candidates)

    @mock.patch("tts.httpx.get")
    def test_external_url_candidates_include_common_mounts(self, mock_get):
        mock_get.side_effect = RuntimeError("offline")
        candidates = TTSEngine._external_url_candidates("localhost:42003")
        self.assertIn("http://localhost:42003/gradio", candidates)
        self.assertIn("http://localhost:42003/gradio_api", candidates)

    @mock.patch("tts.httpx.get")
    def test_detects_qwen_mlx_http_api(self, mock_get):
        mock_response = mock.Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "paths": {
                "/api/v1/custom-voice/generate": {},
                "/api/v1/base/clone": {},
            }
        }
        mock_get.return_value = mock_response
        engine = TTSEngine({
            "llm": {"api_key": "k"},
            "tts": {"mode": "external", "url": "localhost:42003"},
        })
        self.assertEqual(engine._detect_external_http_api(), "http://localhost:42003")

    def test_write_base64_audio(self):
        payload = base64.b64encode(b"RIFFfakewav").decode("ascii")
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            TTSEngine._write_base64_audio(payload, path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"RIFFfakewav")
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
