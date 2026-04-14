import unittest
from types import SimpleNamespace

from llm.structured_service import StructuredLLMService


class StructuredLLMServiceTests(unittest.TestCase):
    def test_extract_tool_arguments_from_tool_calls(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(
                                    arguments='{"voice":"Warm and measured"}'
                                )
                            )
                        ],
                        reasoning_content="",
                    )
                )
            ]
        )

        payload = StructuredLLMService._extract_tool_arguments(response)
        self.assertEqual(payload, {"voice": "Warm and measured"})

    def test_extract_tool_arguments_from_reasoning_content_tags(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[],
                        reasoning_content=(
                            "<tool_call>\n"
                            "<function=submit_script_entries>\n"
                            "<parameter=entries>\n"
                            '[{"speaker":"NARRATOR","text":"Hello","instruct":"Calm."}]'
                            "\n</parameter>\n"
                            "</function>\n"
                            "</tool_call>"
                        ),
                    )
                )
            ]
        )

        payload = StructuredLLMService._extract_tool_arguments(response)
        self.assertIsInstance(payload, dict)
        self.assertIn("entries", payload)
        self.assertIsInstance(payload["entries"], list)
        self.assertEqual(payload["entries"][0]["speaker"], "NARRATOR")

    def test_extract_tool_arguments_returns_none_when_missing(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[], reasoning_content=""))]
        )
        self.assertIsNone(StructuredLLMService._extract_tool_arguments(response))


if __name__ == "__main__":
    unittest.main()
