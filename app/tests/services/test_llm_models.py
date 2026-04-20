import unittest

from llm.models import LLMRuntimeConfig


class LLMRuntimeConfigTests(unittest.TestCase):
    def test_from_dict_trims_api_key_and_model_name(self):
        runtime = LLMRuntimeConfig.from_dict(
            {
                "base_url": "https://openrouter.ai/api/v1 ",
                "api_key": " sk-test-key \n",
                "model_name": " openrouter/elephant-alpha \t",
            }
        )

        self.assertEqual(runtime.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(runtime.api_key, "sk-test-key")
        self.assertEqual(runtime.model_name, "openrouter/elephant-alpha")


if __name__ == "__main__":
    unittest.main()
