"""LM Studio model-load helpers for forcing runtime load configuration."""

from typing import Any, Callable, Dict, Optional

import requests

from .tool_capability_service import ToolCapabilityService


class LMStudioModelLoadService:
    """Load an LM Studio model with explicit runtime configuration."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 120,
        request_json_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
        post_json_fn: Optional[Callable[[str, Dict[str, Any], str], Dict[str, Any]]] = None,
    ):
        self._timeout_seconds = timeout_seconds
        self._request_json_fn = request_json_fn or self._request_json
        self._post_json_fn = post_json_fn or self._post_json

    def load_model(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        context_length: Optional[int] = None,
        eval_batch_size: Optional[int] = None,
        flash_attention: Optional[bool] = None,
        num_experts: Optional[int] = None,
        offload_kv_cache_to_gpu: Optional[bool] = None,
        echo_load_config: bool = False,
    ) -> Dict[str, Any]:
        model = str(model_name or "").strip()
        if not model:
            raise ValueError("model_name is required")

        origin = ToolCapabilityService.normalize_lm_studio_origin(base_url)
        if not origin:
            raise ValueError("base_url is required")

        payload: Dict[str, Any] = {"model": model}
        optional_fields = {
            "context_length": context_length,
            "eval_batch_size": eval_batch_size,
            "flash_attention": flash_attention,
            "num_experts": num_experts,
            "offload_kv_cache_to_gpu": offload_kv_cache_to_gpu,
            "echo_load_config": True if echo_load_config else None,
        }
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value

        return self._post_json_fn(f"{origin}/api/v1/models/load", payload, api_key)

    def list_models(self, *, base_url: str, api_key: str) -> Dict[str, Any]:
        origin = ToolCapabilityService.normalize_lm_studio_origin(base_url)
        if not origin:
            raise ValueError("base_url is required")
        return self._request_json_fn(f"{origin}/api/v1/models", api_key)

    def unload_model_instance(self, *, base_url: str, api_key: str, instance_id: str) -> Dict[str, Any]:
        origin = ToolCapabilityService.normalize_lm_studio_origin(base_url)
        if not origin:
            raise ValueError("base_url is required")
        target = str(instance_id or "").strip()
        if not target:
            raise ValueError("instance_id is required")
        return self._post_json_fn(f"{origin}/api/v1/models/unload", {"instance_id": target}, api_key)

    def unload_all_models(self, *, base_url: str, api_key: str) -> Dict[str, Any]:
        payload = self.list_models(base_url=base_url, api_key=api_key)
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise RuntimeError("LM Studio returned an unexpected model list while unloading.")

        instance_ids = []
        for model in models:
            if not isinstance(model, dict):
                continue
            for instance in model.get("loaded_instances") or []:
                if not isinstance(instance, dict):
                    continue
                instance_id = str(instance.get("id") or "").strip()
                if instance_id:
                    instance_ids.append(instance_id)

        ordered_ids = sorted(set(instance_ids))
        failures = []
        unloaded_ids = []
        for instance_id in ordered_ids:
            try:
                response = self.unload_model_instance(
                    base_url=base_url,
                    api_key=api_key,
                    instance_id=instance_id,
                )
                returned_id = str((response or {}).get("instance_id") or "").strip()
                unloaded_ids.append(returned_id or instance_id)
            except Exception as exc:
                failures.append({
                    "instance_id": instance_id,
                    "error": str(exc),
                })

        if failures:
            raise RuntimeError(f"Failed to unload one or more LM Studio models: {failures}")

        return {
            "status": "ok",
            "total_loaded_instances": len(ordered_ids),
            "unloaded_instance_ids": unloaded_ids,
        }

    @staticmethod
    def auth_headers(api_key: str) -> Dict[str, str]:
        key = str(api_key or "").strip()
        if not key or key.lower() == "local":
            return {}
        return {"Authorization": f"Bearer {key}"}

    def _post_json(self, url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        response = requests.post(
            url,
            headers=self.auth_headers(api_key),
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _request_json(self, url: str, api_key: str) -> Dict[str, Any]:
        response = requests.get(
            url,
            headers=self.auth_headers(api_key),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
