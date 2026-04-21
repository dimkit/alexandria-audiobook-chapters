import asyncio
import json
import os
import tempfile
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

    def test_lm_studio_model_load_posts_expected_payload(self):
        with mock.patch.object(config_router, "_post_json", return_value={"status": "loaded"}) as mock_post:
            result = config_router.load_lmstudio_model(
                base_url="http://localhost:1234/v1",
                api_key="local",
                model_name="qwen/qwen3.5-9b",
                context_length=8192,
                flash_attention=True,
                echo_load_config=True,
            )
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(mock_post.call_count, 1)
        call_args = mock_post.call_args[0]
        self.assertEqual(call_args[0], "http://localhost:1234/api/v1/models/load")
        self.assertEqual(call_args[1]["model"], "qwen/qwen3.5-9b")
        self.assertEqual(call_args[1]["context_length"], 8192)
        self.assertTrue(call_args[1]["flash_attention"])
        self.assertTrue(call_args[1]["echo_load_config"])

    def test_lm_studio_model_load_endpoint_uses_saved_defaults(self):
        with (
            mock.patch.object(
                config_router,
                "_read_saved_llm_config",
                return_value={
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_key": "local",
                    "model_name": "saved/model",
                },
            ),
            mock.patch.object(config_router, "load_lmstudio_model", return_value={"status": "loaded"}) as load_mock,
        ):
            result = asyncio.run(
                config_router.load_lmstudio_model_endpoint(
                    config_router.LMStudioModelLoadRequest(context_length=4096)
                )
            )
        self.assertEqual(result["status"], "loaded")
        load_mock.assert_called_once()
        kwargs = load_mock.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:1234/v1")
        self.assertEqual(kwargs["api_key"], "local")
        self.assertEqual(kwargs["model_name"], "saved/model")
        self.assertEqual(kwargs["context_length"], 4096)

    def test_lm_studio_model_load_endpoint_requires_model(self):
        with mock.patch.object(config_router, "_read_saved_llm_config", return_value={"base_url": "http://127.0.0.1:1234/v1"}):
            with self.assertRaises(config_router.HTTPException) as ctx:
                asyncio.run(
                    config_router.load_lmstudio_model_endpoint(
                        config_router.LMStudioModelLoadRequest()
                    )
                )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Model name is required", str(ctx.exception.detail))

    def test_lm_studio_unload_all_models_unloads_loaded_instances(self):
        with (
            mock.patch.object(
                config_router,
                "_lmstudio_request_json",
                return_value={
                    "models": [
                        {
                            "key": "qwen",
                            "loaded_instances": [{"id": "qwen/instance"}],
                        },
                        {
                            "key": "gemma",
                            "loaded_instances": [{"id": "gemma/instance"}],
                        },
                    ]
                },
            ),
            mock.patch.object(config_router, "_post_json", return_value={"instance_id": "ok"}) as post_mock,
        ):
            result = config_router.unload_all_lmstudio_models(
                base_url="http://127.0.0.1:1234/v1",
                api_key="local",
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_loaded_instances"], 2)
        self.assertEqual(post_mock.call_count, 2)
        posted_payloads = [call[0][1] for call in post_mock.call_args_list]
        self.assertEqual(
            sorted(payload["instance_id"] for payload in posted_payloads),
            ["gemma/instance", "qwen/instance"],
        )

    def test_lm_studio_unload_all_models_endpoint_uses_saved_defaults(self):
        with (
            mock.patch.object(
                config_router,
                "_read_saved_llm_config",
                return_value={
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_key": "local",
                },
            ),
            mock.patch.object(
                config_router,
                "unload_all_lmstudio_models",
                return_value={"status": "ok", "total_loaded_instances": 0, "unloaded_instance_ids": []},
            ) as unload_mock,
        ):
            result = asyncio.run(
                config_router.unload_all_lmstudio_models_endpoint(
                    config_router.LMStudioUnloadAllModelsRequest()
                )
            )

        self.assertEqual(result["status"], "ok")
        unload_mock.assert_called_once()
        kwargs = unload_mock.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:1234/v1")
        self.assertEqual(kwargs["api_key"], "local")

    def test_lm_studio_list_models_normalizes_payload(self):
        with mock.patch.object(
            config_router,
            "_lmstudio_request_json",
            return_value={
                "models": [
                    {
                        "key": "qwen/qwen3.5-9b",
                        "display_name": "Qwen3.5 9B",
                        "loaded_instances": [{"id": "qwen-instance"}, {"id": "qwen-instance"}],
                        "capabilities": {"trained_for_tool_use": True},
                    },
                    {
                        "key": "gemma/gemma-3",
                        "display_name": "Gemma 3",
                        "loaded_instances": [],
                        "capabilities": {},
                    },
                ]
            },
        ):
            result = config_router.list_lmstudio_models(
                base_url="http://127.0.0.1:1234/v1",
                api_key="local",
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["models"][0],
            {
                "key": "qwen/qwen3.5-9b",
                "display_name": "Qwen3.5 9B",
                "loaded_instance_ids": ["qwen-instance"],
                "trained_for_tool_use": True,
            },
        )
        self.assertEqual(
            result["models"][1],
            {
                "key": "gemma/gemma-3",
                "display_name": "Gemma 3",
                "loaded_instance_ids": [],
                "trained_for_tool_use": None,
            },
        )

    def test_lm_studio_list_models_endpoint_uses_saved_defaults(self):
        with (
            mock.patch.object(
                config_router,
                "_read_saved_llm_config",
                return_value={
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_key": "local",
                },
            ),
            mock.patch.object(
                config_router,
                "list_lmstudio_models",
                return_value={"status": "ok", "models": []},
            ) as list_mock,
        ):
            result = asyncio.run(
                config_router.list_lmstudio_models_endpoint(
                    config_router.LMStudioListModelsRequest()
                )
            )

        self.assertEqual(result["status"], "ok")
        list_mock.assert_called_once()
        kwargs = list_mock.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:1234/v1")
        self.assertEqual(kwargs["api_key"], "local")

    def test_lm_studio_list_models_endpoint_returns_502_on_failure(self):
        with mock.patch.object(config_router, "list_lmstudio_models", side_effect=RuntimeError("offline")):
            with self.assertRaises(config_router.HTTPException) as ctx:
                asyncio.run(
                    config_router.list_lmstudio_models_endpoint(
                        config_router.LMStudioListModelsRequest(
                            base_url="http://127.0.0.1:1234/v1",
                            api_key="local",
                        )
                    )
                )
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("Failed to list LM Studio models", str(ctx.exception.detail))


class LLMGatewayCacheInvalidationTests(unittest.TestCase):
    def _base_config_payload(self):
        return {
            "llm": {
                "base_url": "http://localhost:1234/v1",
                "api_key": "local",
                "model_name": "model-a",
                "llm_workers": 1,
            },
            "tts": {
                "mode": "external",
                "url": "http://127.0.0.1:7860",
                "device": "auto",
                "language": "English",
                "parallel_workers": 4,
                "script_max_length": 250,
            },
            "prompts": {},
            "generation": {},
        }

    def test_save_config_clears_gateway_cache_when_model_changes(self):
        with tempfile.TemporaryDirectory() as temp_root:
            config_path = os.path.join(temp_root, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(self._base_config_payload(), handle, indent=2, ensure_ascii=False)

            updated = self._base_config_payload()
            updated["llm"]["model_name"] = "model-b"

            with (
                mock.patch.object(config_router, "CONFIG_PATH", config_path),
                mock.patch.object(config_router, "_sync_prompt_files", return_value={}),
                mock.patch.object(config_router, "clear_llm_gateway_cache") as clear_mock,
            ):
                result = asyncio.run(config_router.save_config(config_router.AppConfig(**updated)))

            self.assertEqual(result["status"], "saved")
            self.assertTrue(result["llm_cache_cleared"])
            clear_mock.assert_called_once()

    def test_save_config_does_not_clear_gateway_cache_when_llm_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_root:
            config_path = os.path.join(temp_root, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(self._base_config_payload(), handle, indent=2, ensure_ascii=False)

            updated = self._base_config_payload()

            with (
                mock.patch.object(config_router, "CONFIG_PATH", config_path),
                mock.patch.object(config_router, "_sync_prompt_files", return_value={}),
                mock.patch.object(config_router, "clear_llm_gateway_cache") as clear_mock,
            ):
                result = asyncio.run(config_router.save_config(config_router.AppConfig(**updated)))

            self.assertEqual(result["status"], "saved")
            self.assertFalse(result["llm_cache_cleared"])
            clear_mock.assert_not_called()

    def test_save_setup_config_clears_gateway_cache_when_base_url_changes(self):
        with tempfile.TemporaryDirectory() as temp_root:
            config_path = os.path.join(temp_root, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(self._base_config_payload(), handle, indent=2, ensure_ascii=False)

            update = config_router.SetupConfigUpdate(
                llm=config_router.LLMConfig(
                    base_url="http://localhost:2234/v1",
                    api_key="local",
                    model_name="model-a",
                    llm_workers=1,
                )
            )

            with (
                mock.patch.object(config_router, "CONFIG_PATH", config_path),
                mock.patch.object(config_router, "clear_llm_gateway_cache") as clear_mock,
            ):
                result = asyncio.run(config_router.save_setup_config(update))

            self.assertEqual(result["status"], "saved")
            self.assertTrue(result["llm_cache_cleared"])
            clear_mock.assert_called_once()

    def test_save_setup_config_does_not_clear_cache_for_equivalent_base_url(self):
        with tempfile.TemporaryDirectory() as temp_root:
            config_path = os.path.join(temp_root, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(self._base_config_payload(), handle, indent=2, ensure_ascii=False)

            update = config_router.SetupConfigUpdate(
                llm=config_router.LLMConfig(
                    base_url="http://localhost:1234",
                    api_key="local",
                    model_name="model-a",
                    llm_workers=1,
                )
            )

            with (
                mock.patch.object(config_router, "CONFIG_PATH", config_path),
                mock.patch.object(config_router, "clear_llm_gateway_cache") as clear_mock,
            ):
                result = asyncio.run(config_router.save_setup_config(update))

            self.assertEqual(result["status"], "saved")
            self.assertFalse(result["llm_cache_cleared"])
            clear_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
