"""Shared app-wide LLM gateway singleton."""

from .structured_service import StructuredLLMService

_LLM_GATEWAY = StructuredLLMService()


def get_llm_gateway() -> StructuredLLMService:
    """Return the process-global structured LLM gateway instance."""
    return _LLM_GATEWAY


def clear_llm_gateway_cache() -> None:
    """Clear process-global capability/mode cache for the LLM gateway."""
    _LLM_GATEWAY.clear_cache()

