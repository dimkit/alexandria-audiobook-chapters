"""Streaming helper for forced tool-call workflows."""

import json
import re
from typing import Any, Dict, List, Optional

from .errors import LLMTransportError
from .models import ToolStreamResult


class ToolStreamingService:
    """Stream chat-completions tool calls and extract the first parseable tool args."""

    def stream_required_tool_call(
        self,
        *,
        client: Any,
        model_name: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        tool_choice: Any = "required",
        parallel_tool_calls: bool = False,
        reasoning_parameter_name: Optional[str] = None,
    ) -> ToolStreamResult:
        tool_call_args = ""
        reasoning_content = ""
        tool_call_observed = False

        try:
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
                "parallel_tool_calls": parallel_tool_calls,
                "temperature": temperature,
                "stream": True,
            }
            if max_tokens is not None:
                payload["max_tokens"] = int(max_tokens)

            stream = client.chat.completions.create(
                **payload,
            )
        except Exception as exc:
            raise LLMTransportError(f"Failed to start streamed LLM request: {exc}") from exc

        try:
            for chunk in stream:
                choices = self._field(chunk, "choices") or []
                if not choices:
                    continue
                delta = self._field(choices[0], "delta")
                if delta is None:
                    continue

                rc = self._field(delta, "reasoning_content")
                if rc:
                    reasoning_content += str(rc)

                delta_tool_calls = self._field(delta, "tool_calls") or []
                if delta_tool_calls:
                    tool_call_observed = True
                    function = self._field(delta_tool_calls[0], "function")
                    frag = self._field(function, "arguments") if function is not None else None
                    if frag:
                        tool_call_args += frag

                legacy_function_call = self._field(delta, "function_call")
                if legacy_function_call is not None:
                    tool_call_observed = True
                    frag = self._field(legacy_function_call, "arguments")
                    if frag:
                        tool_call_args += frag

                parsed = self._try_parse_json(tool_call_args)
                if parsed is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                    return ToolStreamResult(
                        parsed_arguments=parsed,
                        tool_call_observed=tool_call_observed,
                        raw_payload=tool_call_args,
                        reasoning_content=reasoning_content,
                    )

            parsed = self._try_parse_json(tool_call_args)
            if parsed is not None:
                return ToolStreamResult(
                    parsed_arguments=parsed,
                    tool_call_observed=tool_call_observed,
                    raw_payload=tool_call_args,
                    reasoning_content=reasoning_content,
                )

            reasoning_payload = self._extract_reasoning_parameters(reasoning_content)
            if reasoning_payload:
                if reasoning_parameter_name:
                    if reasoning_parameter_name in reasoning_payload:
                        return ToolStreamResult(
                            parsed_arguments={reasoning_parameter_name: reasoning_payload[reasoning_parameter_name]},
                            tool_call_observed=True,
                            raw_payload=reasoning_content,
                            reasoning_content=reasoning_content,
                        )
                else:
                    return ToolStreamResult(
                        parsed_arguments=reasoning_payload,
                        tool_call_observed=True,
                        raw_payload=reasoning_content,
                        reasoning_content=reasoning_content,
                    )
        except Exception as exc:
            raise LLMTransportError(f"Streamed LLM request failed: {exc}") from exc

        parsed = self._try_parse_json(tool_call_args)
        if parsed is not None:
            return ToolStreamResult(
                parsed_arguments=parsed,
                tool_call_observed=tool_call_observed,
                raw_payload=tool_call_args,
                reasoning_content=reasoning_content,
            )

        reasoning_payload = self._extract_reasoning_parameters(reasoning_content)
        if reasoning_payload:
            if reasoning_parameter_name:
                if reasoning_parameter_name in reasoning_payload:
                    return ToolStreamResult(
                        parsed_arguments={reasoning_parameter_name: reasoning_payload[reasoning_parameter_name]},
                        tool_call_observed=True,
                        raw_payload=reasoning_content,
                        reasoning_content=reasoning_content,
                    )
            else:
                return ToolStreamResult(
                    parsed_arguments=reasoning_payload,
                    tool_call_observed=True,
                    raw_payload=reasoning_content,
                    reasoning_content=reasoning_content,
                )

        return ToolStreamResult(
            parsed_arguments=None,
            tool_call_observed=tool_call_observed,
            raw_payload=tool_call_args,
            reasoning_content=reasoning_content,
        )

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _try_parse_json(payload: str) -> Optional[Dict[str, Any]]:
        if not payload:
            return None
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _extract_reasoning_parameters(reasoning_content: str) -> Optional[Dict[str, Any]]:
        content = str(reasoning_content or "").strip()
        if not content:
            return None

        matches = re.findall(
            r"<parameter=([A-Za-z0-9_:-]+)>([\s\S]*?)</parameter>",
            content,
            flags=re.IGNORECASE,
        )
        if not matches:
            return None

        parsed: Dict[str, Any] = {}
        for raw_name, raw_value in matches:
            name = str(raw_name or "").strip()
            if not name:
                continue
            value = str(raw_value or "").strip()
            if not value:
                parsed[name] = ""
                continue
            maybe_json = ToolStreamingService._try_parse_json(value)
            parsed[name] = maybe_json if maybe_json is not None else value
        return parsed or None
