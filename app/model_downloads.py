"""Shared model download tracking for app-controlled Hugging Face downloads."""

from __future__ import annotations

import os
import queue
import shutil
import threading
import time
import uuid
import glob
from typing import Any, Callable, Dict, Optional


TRUE_VALUES = {"1", "true", "yes", "on"}


def downloads_disabled() -> bool:
    return str(os.getenv("THREADSPEAK_DISABLE_MODEL_DOWNLOADS", "")).strip().lower() in TRUE_VALUES


class ModelDownloadManager:
    def __init__(
        self,
        *,
        clear_completed_after_seconds: float = 4.0,
        publish_interval_seconds: float = 0.5,
        time_fn: Callable[[], float] = time.time,
    ):
        self._clear_completed_after_seconds = max(0.0, float(clear_completed_after_seconds))
        self._publish_interval_seconds = max(0.05, float(publish_interval_seconds))
        self._time_fn = time_fn
        self._lock = threading.Lock()
        self._downloads: Dict[str, Dict[str, Any]] = {}
        self._retry_specs: Dict[str, Dict[str, Any]] = {}
        self._subscribers: Dict[str, queue.Queue] = {}

    def ensure_hf_snapshot(
        self,
        repo_id: str,
        *,
        display_name: Optional[str] = None,
        local_path_resolver: Optional[Callable[[str, Any], Optional[str]]] = None,
        required_files: Any = None,
        snapshot_download_fn: Optional[Callable[..., str]] = None,
        **kwargs,
    ) -> str:
        repo = str(repo_id or "").strip()
        if not repo:
            raise ValueError("repo_id is required")

        if local_path_resolver is not None:
            local_path = local_path_resolver(repo, required_files)
            if local_path:
                return local_path

        self._raise_if_disabled(repo)
        operation = {
            "kind": "snapshot",
            "repo_id": repo,
            "display_name": display_name or repo,
            "snapshot_download_fn": snapshot_download_fn,
            "kwargs": dict(kwargs),
            "required_files": required_files,
        }
        return self._run_snapshot(operation)

    def download_hf_file(
        self,
        *,
        repo_id: str,
        filename: str,
        display_name: Optional[str] = None,
        local_path: Optional[str] = None,
        hf_hub_download_fn: Optional[Callable[..., str]] = None,
        record_failures: bool = True,
        **kwargs,
    ) -> str:
        repo = str(repo_id or "").strip()
        target = str(filename or "").strip()
        if not repo:
            raise ValueError("repo_id is required")
        if not target:
            raise ValueError("filename is required")
        if local_path and os.path.exists(local_path):
            return local_path

        self._raise_if_disabled(repo)
        operation = {
            "kind": "file",
            "repo_id": repo,
            "filename": target,
            "display_name": display_name or repo,
            "local_path": local_path,
            "hf_hub_download_fn": hf_hub_download_fn,
            "record_failures": bool(record_failures),
            "kwargs": dict(kwargs),
        }
        return self._run_file(operation)

    def retry_download(self, download_id: str) -> Dict[str, Any]:
        download_id = str(download_id or "").strip()
        with self._lock:
            spec = dict(self._retry_specs.get(download_id) or {})
            current = self._downloads.get(download_id)
            if not spec or not current:
                raise KeyError(download_id)
            if current.get("status") != "failed":
                raise ValueError("Only failed downloads can be retried.")

        if spec.get("kind") == "snapshot":
            self._run_snapshot(spec, download_id=download_id)
        elif spec.get("kind") == "file":
            self._run_file(spec, download_id=download_id)
        else:
            raise ValueError("Unsupported retry operation.")

        with self._lock:
            return dict(self._downloads.get(download_id) or {"id": download_id, "status": "unknown"})

    def snapshot(self, *, include_completed: bool = False) -> Dict[str, Any]:
        with self._lock:
            self._prune_completed_locked()
            downloads = [
                self._serialize_download_locked(item, include_completed=include_completed)
                for item in self._downloads.values()
                if include_completed or item.get("status") != "completed" or not self._is_completed_expired_locked(item)
            ]
        downloads.sort(key=lambda item: (item.get("started_at") or 0.0, item.get("id") or ""))
        return {"downloads": downloads}

    def subscribe(self):
        subscriber_id = uuid.uuid4().hex
        subscriber_queue = queue.Queue(maxsize=128)
        with self._lock:
            self._subscribers[subscriber_id] = subscriber_queue
        return subscriber_id, subscriber_queue

    def unsubscribe(self, subscriber_id):
        with self._lock:
            self._subscribers.pop(str(subscriber_id or ""), None)

    def _run_snapshot(self, operation: Dict[str, Any], *, download_id: Optional[str] = None) -> str:
        from huggingface_hub import snapshot_download

        repo = operation["repo_id"]
        download_id = self._begin_download(
            download_id=download_id,
            repo_id=repo,
            display_name=operation["display_name"],
            operation=operation,
        )
        tqdm_class = self._tqdm_class(download_id, fallback_filename=repo)
        try:
            fn = operation.get("snapshot_download_fn") or snapshot_download
            result = fn(repo_id=repo, tqdm_class=tqdm_class, **dict(operation.get("kwargs") or {}))
            if not self._snapshot_has_required_files(result, operation.get("required_files")):
                raise RuntimeError(
                    f"Downloaded snapshot for {repo} is missing required model files."
                )
            self._complete_download(download_id)
            return result
        except Exception as exc:
            self._fail_download(download_id, exc)
            raise

    def _run_file(self, operation: Dict[str, Any], *, download_id: Optional[str] = None) -> str:
        from huggingface_hub import hf_hub_download

        repo = operation["repo_id"]
        filename = operation["filename"]
        download_id = self._begin_download(
            download_id=download_id,
            repo_id=repo,
            display_name=operation["display_name"],
            operation=operation,
        )
        tqdm_class = self._tqdm_class(download_id, fallback_filename=filename)
        try:
            fn = operation.get("hf_hub_download_fn") or hf_hub_download
            cached = fn(repo_id=repo, filename=filename, tqdm_class=tqdm_class, **dict(operation.get("kwargs") or {}))
            local_path = operation.get("local_path")
            if local_path:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                if os.path.abspath(cached) != os.path.abspath(local_path):
                    shutil.copy2(cached, local_path)
                result = local_path
            else:
                result = cached
            self._complete_download(download_id)
            return result
        except Exception as exc:
            if operation.get("record_failures", True):
                self._ensure_file_row(download_id, filename)
                self._fail_download(download_id, exc)
            else:
                self._discard_download(download_id)
            raise

    def _begin_download(self, *, download_id: Optional[str], repo_id: str, display_name: str, operation: Dict[str, Any]) -> str:
        now = self._time_fn()
        download_id = download_id or uuid.uuid4().hex
        with self._lock:
            self._downloads[download_id] = {
                "id": download_id,
                "repo_id": repo_id,
                "display_name": display_name,
                "status": "active",
                "started_at": now,
                "updated_at": now,
                "completed_at": None,
                "error": "",
                "files": {},
                "retryable": False,
                "last_published_at": now,
            }
            self._retry_specs[download_id] = dict(operation)
        self._publish()
        return download_id

    def _complete_download(self, download_id: str):
        with self._lock:
            item = self._downloads.get(download_id)
            if not item:
                return
            now = self._time_fn()
            for row in item["files"].values():
                if row.get("total_bytes") and row.get("downloaded_bytes", 0) < row.get("total_bytes", 0):
                    row["downloaded_bytes"] = row["total_bytes"]
                row["status"] = "completed"
                row["eta_seconds"] = 0
                row["updated_at"] = now
            item["status"] = "completed"
            item["updated_at"] = now
            item["completed_at"] = now
            item["error"] = ""
            item["retryable"] = False
        self._publish()

    def _fail_download(self, download_id: str, exc: Exception):
        with self._lock:
            item = self._downloads.get(download_id)
            if not item:
                return
            now = self._time_fn()
            error = str(exc)
            item["status"] = "failed"
            item["updated_at"] = now
            item["completed_at"] = None
            item["error"] = error
            item["retryable"] = True
            for row in item["files"].values():
                if row.get("status") != "completed":
                    row["status"] = "failed"
                    row["error"] = error
                    row["updated_at"] = now
        self._publish()

    def _discard_download(self, download_id: str):
        with self._lock:
            self._downloads.pop(download_id, None)
            self._retry_specs.pop(download_id, None)
        self._publish()

    def _tqdm_class(self, download_id: str, *, fallback_filename: str):
        manager = self

        class DownloadProgress:
            _lock = threading.RLock()

            @classmethod
            def get_lock(cls):
                return cls._lock

            @classmethod
            def set_lock(cls, lock):
                cls._lock = lock

            def __init__(self, *args, **kwargs):
                self.iterable = args[0] if args else kwargs.get("iterable")
                self.total = int(kwargs.get("total") or 0)
                self.n = int(kwargs.get("initial") or 0)
                desc = kwargs.get("desc") or kwargs.get("filename") or fallback_filename
                self._row_id = uuid.uuid4().hex
                self._last_bytes = self.n
                self._last_time = manager._time_fn()
                unit = str(kwargs.get("unit") or "").strip()
                self._track_bytes = unit == "B" or bool(kwargs.get("unit_scale") and str(desc or "").startswith("Downloading"))
                if self._track_bytes:
                    manager._update_file(
                        download_id,
                        self._row_id,
                        filename=manager._progress_filename(str(desc or ""), fallback_filename),
                        downloaded_bytes=self.n,
                        total_bytes=self.total,
                        speed_bps=0.0,
                        status="active",
                    )

            def update(self, n=1):
                now = manager._time_fn()
                increment = int(n or 0)
                self.n += increment
                if not self._track_bytes:
                    return None
                elapsed = max(0.001, now - self._last_time)
                speed = max(0.0, float(self.n - self._last_bytes) / elapsed)
                self._last_time = now
                self._last_bytes = self.n
                manager._update_file(
                    download_id,
                    self._row_id,
                    filename=fallback_filename,
                    downloaded_bytes=self.n,
                    total_bytes=self.total,
                    speed_bps=speed,
                    status="active",
                )

            def close(self):
                if self._track_bytes:
                    manager._complete_file(download_id, self._row_id)

            def refresh(self):
                if self._track_bytes:
                    manager._update_file(
                        download_id,
                        self._row_id,
                        filename=fallback_filename,
                        downloaded_bytes=self.n,
                        total_bytes=self.total,
                        speed_bps=0.0,
                        status="active",
                    )
                return None

            def reset(self, total=None):
                if total is not None:
                    self.total = int(total or 0)
                    self.refresh()

            def set_description(self, desc=None, refresh=True):
                if self._track_bytes:
                    manager._rename_file(download_id, self._row_id, manager._progress_filename(str(desc or ""), fallback_filename))

            def set_postfix(self, *args, **kwargs):
                return None

            def __iter__(self):
                if self.iterable is None:
                    return iter(())
                for item in self.iterable:
                    yield item
                    self.update(1)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()
                return False

        return DownloadProgress

    @staticmethod
    def _progress_filename(desc: str, fallback_filename: str) -> str:
        text = str(desc or "").strip()
        if not text or text.startswith("Downloading") or text.startswith("Download complete"):
            return str(fallback_filename or "model weights")
        return text

    def _update_file(
        self,
        download_id: str,
        row_id: str,
        *,
        filename: str,
        downloaded_bytes: int,
        total_bytes: int,
        speed_bps: float,
        status: str,
    ):
        with self._lock:
            item = self._downloads.get(download_id)
            if not item:
                return
            now = self._time_fn()
            row = item["files"].setdefault(
                row_id,
                {
                    "id": row_id,
                    "filename": filename,
                    "started_at": now,
                    "error": "",
                },
            )
            if filename and (not row.get("filename") or row.get("filename") == item.get("repo_id")):
                row["filename"] = filename
            row["downloaded_bytes"] = max(0, int(downloaded_bytes or 0))
            row["total_bytes"] = max(0, int(total_bytes or 0))
            row["speed_bps"] = max(0.0, float(speed_bps or 0.0))
            remaining = max(0, row["total_bytes"] - row["downloaded_bytes"])
            row["eta_seconds"] = int(remaining / row["speed_bps"]) if row["speed_bps"] > 0 and row["total_bytes"] else None
            row["status"] = status
            row["updated_at"] = now
            item["updated_at"] = now
        self._publish_progress(download_id)

    def _rename_file(self, download_id: str, row_id: str, filename: str):
        with self._lock:
            row = ((self._downloads.get(download_id) or {}).get("files") or {}).get(row_id)
            if row:
                row["filename"] = filename
        self._publish_progress(download_id)

    def _complete_file(self, download_id: str, row_id: str):
        with self._lock:
            row = ((self._downloads.get(download_id) or {}).get("files") or {}).get(row_id)
            if row:
                if row.get("total_bytes") and row.get("downloaded_bytes", 0) < row.get("total_bytes", 0):
                    row["downloaded_bytes"] = row["total_bytes"]
                row["status"] = "completed"
                row["eta_seconds"] = 0
                row["updated_at"] = self._time_fn()
        self._publish_progress(download_id)

    def _ensure_file_row(self, download_id: str, filename: str):
        with self._lock:
            item = self._downloads.get(download_id)
            if not item or item["files"]:
                return
            now = self._time_fn()
            item["files"]["default"] = {
                "id": "default",
                "filename": filename,
                "status": "failed",
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "speed_bps": 0.0,
                "eta_seconds": None,
                "started_at": now,
                "updated_at": now,
                "error": "",
            }

    @staticmethod
    def _snapshot_has_required_files(snapshot_path: str, required_files: Any) -> bool:
        if not required_files:
            return True
        root = str(snapshot_path or "").strip()
        if not root or not os.path.isdir(root):
            return False

        def requirement_exists(requirement: Any) -> bool:
            text = str(requirement or "").strip()
            if not text:
                return False
            if glob.has_magic(text):
                return any(os.path.isfile(path) for path in glob.glob(os.path.join(root, text)))
            return os.path.exists(os.path.join(root, text))

        for requirement in required_files:
            if isinstance(requirement, (list, tuple, set)):
                if not any(requirement_exists(item) for item in requirement):
                    return False
            elif not requirement_exists(requirement):
                return False
        return True

    def _serialize_download_locked(self, item: Dict[str, Any], *, include_completed: bool) -> Dict[str, Any]:
        files = [dict(row) for row in item.get("files", {}).values()]
        files.sort(key=lambda row: (row.get("started_at") or 0.0, row.get("filename") or ""))
        downloaded = sum(int(row.get("downloaded_bytes") or 0) for row in files)
        total = sum(int(row.get("total_bytes") or 0) for row in files)
        speed = sum(float(row.get("speed_bps") or 0.0) for row in files)
        remaining = max(0, total - downloaded)
        eta = int(remaining / speed) if speed > 0 and total else 0 if total and downloaded >= total else None
        return {
            "id": item.get("id"),
            "repo_id": item.get("repo_id"),
            "display_name": item.get("display_name") or item.get("repo_id"),
            "status": item.get("status"),
            "started_at": item.get("started_at"),
            "updated_at": item.get("updated_at"),
            "completed_at": item.get("completed_at"),
            "error": item.get("error") or "",
            "retryable": bool(item.get("retryable")),
            "downloaded_bytes": downloaded,
            "total_bytes": total,
            "speed_bps": speed,
            "eta_seconds": eta,
            "files": files,
        }

    def _is_completed_expired_locked(self, item: Dict[str, Any]) -> bool:
        if item.get("status") != "completed":
            return False
        completed_at = float(item.get("completed_at") or 0.0)
        return completed_at > 0 and (self._time_fn() - completed_at) >= self._clear_completed_after_seconds

    def _prune_completed_locked(self):
        expired = [
            download_id
            for download_id, item in self._downloads.items()
            if self._is_completed_expired_locked(item)
        ]
        for download_id in expired:
            self._downloads.pop(download_id, None)
            self._retry_specs.pop(download_id, None)

    def _publish(self):
        payload = self.snapshot()
        with self._lock:
            subscribers = list(self._subscribers.items())
        for subscriber_id, subscriber_queue in subscribers:
            try:
                subscriber_queue.put_nowait(payload)
            except queue.Full:
                try:
                    subscriber_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber_queue.put_nowait(payload)
                except queue.Full:
                    self.unsubscribe(subscriber_id)

    def _publish_progress(self, download_id: str):
        with self._lock:
            item = self._downloads.get(download_id)
            if not item:
                return
            now = self._time_fn()
            last = float(item.get("last_published_at") or 0.0)
            if now - last < self._publish_interval_seconds:
                return
            item["last_published_at"] = now
        self._publish()

    @staticmethod
    def _raise_if_disabled(repo_id: str):
        if downloads_disabled():
            raise RuntimeError(
                "Model downloads are disabled by THREADSPEAK_DISABLE_MODEL_DOWNLOADS "
                f"and no local cache exists for {repo_id}."
            )


model_download_manager = ModelDownloadManager()


def ensure_hf_snapshot(repo_id: str, *, display_name: Optional[str] = None, **kwargs) -> str:
    return model_download_manager.ensure_hf_snapshot(repo_id, display_name=display_name, **kwargs)


def download_hf_file(
    repo_id: str,
    filename: str,
    *,
    display_name: Optional[str] = None,
    local_path: Optional[str] = None,
    record_failures: bool = True,
    **kwargs,
) -> str:
    return model_download_manager.download_hf_file(
        repo_id=repo_id,
        filename=filename,
        display_name=display_name,
        local_path=local_path,
        record_failures=record_failures,
        **kwargs,
    )
