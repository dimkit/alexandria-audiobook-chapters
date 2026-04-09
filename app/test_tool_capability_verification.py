import unittest
from unittest import mock

from api.routers import config_router


class ToolCapabilityVerificationTests(unittest.TestCase):
    def test_openrouter_supported_model_match(self):
        with mock.patch.object(config_router, "_request_json", return_value={
            "data": [{"id": "openai/gpt-4.1"}, {"id": "anthropic/claude-sonnet-4"}]
        }):
            result = config_router.verify_tool_capability(
                "https://openrouter.ai/api/v1",
                "sk-test",
                "anthropic/claude-sonnet-4",
            )
        self.assertEqual(result["status"], "supported")
        self.assertTrue(result["supported"])
        self.assertEqual(result["provider"], "openrouter")

    def test_openrouter_absent_model_is_unsupported(self):
        with mock.patch.object(config_router, "_request_json", return_value={
            "data": [{"id": "openai/gpt-4.1"}]
        }):
            result = config_router.verify_tool_capability(
                "https://openrouter.ai/api/v1",
                "sk-test",
                "meta-llama/llama-3",
            )
        self.assertEqual(result["status"], "unsupported")
        self.assertFalse(result["supported"])

    def test_openrouter_failure_is_unknown(self):
        with mock.patch.object(config_router, "_request_json", side_effect=RuntimeError("boom")):
            result = config_router.verify_tool_capability(
                "https://openrouter.ai/api/v1",
                "sk-test",
                "openai/gpt-4.1",
            )
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["supported"])
        self.assertIn("Could not verify", result["message"])

    def test_lm_studio_supported_model_by_key(self):
        payload = {
            "models": [{
                "key": "qwen3-tool",
                "display_name": "Qwen 3 Tool",
                "capabilities": {"trained_for_tool_use": True},
                "loaded_instances": [],
            }]
        }
        with mock.patch.object(config_router, "_request_json", return_value=payload):
            result = config_router.verify_tool_capability(
                "http://localhost:1234/v1",
                "local",
                "qwen3-tool",
            )
        self.assertEqual(result["status"], "supported")
        self.assertTrue(result["supported"])
        self.assertEqual(result["provider"], "lmstudio")

    def test_lm_studio_unsupported_model_by_display_name(self):
        payload = {
            "models": [{
                "key": "gemma-3",
                "display_name": "Gemma 3",
                "capabilities": {"trained_for_tool_use": False},
                "loaded_instances": [],
            }]
        }
        with mock.patch.object(config_router, "_request_json", return_value=payload):
            result = config_router.verify_tool_capability(
                "http://127.0.0.1:1234/v1",
                "",
                "Gemma 3",
            )
        self.assertEqual(result["status"], "unsupported")
        self.assertFalse(result["supported"])

    def test_lm_studio_matches_loaded_instance_id(self):
        payload = {
            "models": [{
                "key": "downloaded-key",
                "display_name": "Downloaded Model",
                "capabilities": {"trained_for_tool_use": True},
                "loaded_instances": [{"id": "currently-loaded-id"}],
            }]
        }
        with mock.patch.object(config_router, "_request_json", return_value=payload):
            result = config_router.verify_tool_capability(
                "http://localhost:1234/v1",
                "",
                "currently-loaded-id",
            )
        self.assertEqual(result["status"], "supported")

    def test_lm_studio_failure_is_unknown(self):
        with mock.patch.object(config_router, "_request_json", side_effect=RuntimeError("offline")):
            result = config_router.verify_tool_capability(
                "http://localhost:1234/v1",
                "",
                "qwen3-tool",
            )
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["supported"])
        self.assertIn("Could not verify", result["message"])


if __name__ == "__main__":
    unittest.main()
