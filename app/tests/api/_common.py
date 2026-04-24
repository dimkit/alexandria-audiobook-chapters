"""Shared state, fixtures, and helpers for API endpoint tests."""

#!/usr/bin/env python3
"""Automated API test script.

Usage:
    python test_api.py        # Quick tests only, always against an isolated server
    python test_api.py --full # Include TTS/LLM-dependent tests
"""

import argparse
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
from pathlib import Path
import requests
from runtime_layout import RuntimeLayout
try:
    import pytest
except Exception:  # pragma: no cover - pytest import only needed when running under pytest
    pytest = None

# ── Global state ─────────────────────────────────────────────

def _normalize_http_url(raw_url):
    url = (raw_url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = f"http://{url}"
    return url.rstrip("/")


def _discover_base_url():
    # Explicit test override wins.
    for key in ("THREADSPEAK_TEST_URL", "BASE_URL"):
        configured = _normalize_http_url(os.getenv(key))
        if configured:
            return configured

    # Pinokio can expose the launched URL through the variable named in PINOKIO_SHARE_VAR.
    # Example: PINOKIO_SHARE_VAR=url and env[url]=http://127.0.0.1:42003
    share_var_key = (os.getenv("PINOKIO_SHARE_VAR") or "").strip()
    if share_var_key:
        shared = _normalize_http_url(os.getenv(share_var_key) or os.getenv(share_var_key.upper()))
        if shared:
            return shared

    # Pinokio local share port is a reliable fallback when no direct URL var is present.
    share_port = (os.getenv("PINOKIO_SHARE_LOCAL_PORT") or "").strip()
    if share_port.isdigit():
        return f"http://127.0.0.1:{share_port}"

    # Legacy fallback.
    return "http://127.0.0.1:4200"


def _assert_no_external_server_target():
    forbidden = []
    for key in ("THREADSPEAK_TEST_URL", "BASE_URL", "THREADSPEAK_TEST_USE_EXTERNAL_SERVER"):
        value = (os.getenv(key) or "").strip()
        if value:
            forbidden.append(f"{key}={value}")
    if forbidden:
        joined = ", ".join(forbidden)
        raise RuntimeError(
            "test_api.py no longer allows targeting an external/live server. "
            f"Unset: {joined}"
        )


BASE_URL = _discover_base_url()
FULL_MODE = (os.getenv("THREADSPEAK_TEST_FULL", "").strip().lower() in {"1", "true", "yes", "on"})
TEST_PREFIX = "_test_"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = str(Path(__file__).resolve().parents[2])
SOURCE_LAYOUT = RuntimeLayout.from_app_dir(APP_DIR)
SOURCE_REPO_DIR = SOURCE_LAYOUT.repo_root
REPO_DIR = SOURCE_LAYOUT.repo_root
PROJECT_DIR = SOURCE_LAYOUT.project_dir
STATE_PATH = SOURCE_LAYOUT.state_path
UPLOADS_PATH = SOURCE_LAYOUT.uploads_dir
ACTIVE_APP_DIR = APP_DIR

results = {"passed": 0, "failed": 0, "skipped": 0}
failures = []
shared = {}  # state shared between dependent tests
_SERVER_PROC = None
_SERVER_TEMP_ROOT = None


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_isolated_test_server():
    global BASE_URL, REPO_DIR, PROJECT_DIR, STATE_PATH, UPLOADS_PATH, ACTIVE_APP_DIR, _SERVER_PROC, _SERVER_TEMP_ROOT

    _SERVER_TEMP_ROOT = tempfile.mkdtemp(prefix="threadspeak_api_test_")
    temp_app_dir = os.path.join(_SERVER_TEMP_ROOT, "app")
    shutil.copytree(
        APP_DIR,
        temp_app_dir,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "env"),
    )
    temp_root = os.path.dirname(temp_app_dir)
    for filename in (
        "default_prompts.txt",
        "review_prompts.txt",
        "attribution_prompts.txt",
        "voice_prompt.txt",
        "dialogue_identification_system_prompt.txt",
        "temperament_extraction_system_prompt.txt",
    ):
        source = os.path.join(SOURCE_REPO_DIR, "config", "prompts", filename)
        if os.path.exists(source):
            prompt_dir = os.path.join(temp_root, "config", "prompts")
            os.makedirs(prompt_dir, exist_ok=True)
            shutil.copy2(source, os.path.join(prompt_dir, filename))

    default_config_path = os.path.join(temp_app_dir, "config.default.json")
    local_config_path = os.path.join(temp_app_dir, "config.json")
    if os.path.exists(default_config_path):
        shutil.copy2(default_config_path, local_config_path)

    port = _find_free_port()
    env = os.environ.copy()
    env["PINOKIO_SHARE_LOCAL"] = "false"
    env["PINOKIO_SHARE_LOCAL_PORT"] = str(port)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    _SERVER_PROC = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=temp_app_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    while time.time() < deadline:
        if _SERVER_PROC.poll() is not None:
            output = ""
            if _SERVER_PROC.stdout:
                try:
                    output = _SERVER_PROC.stdout.read() or ""
                except Exception:
                    output = ""
            raise RuntimeError(f"Isolated test server exited early with code {_SERVER_PROC.returncode}.\n{output[-2000:]}")
        try:
            r = requests.get(f"{base_url}/", timeout=1.5)
            if r.status_code < 500:
                break
        except Exception:
            pass
        time.sleep(0.3)
    else:
        raise RuntimeError(f"Timed out waiting for isolated test server at {base_url}")

    BASE_URL = base_url
    ACTIVE_APP_DIR = temp_app_dir
    layout = RuntimeLayout.from_app_dir(temp_app_dir)
    REPO_DIR = layout.repo_root
    PROJECT_DIR = layout.project_dir
    STATE_PATH = layout.state_path
    UPLOADS_PATH = layout.uploads_dir


def _stop_isolated_test_server():
    global _SERVER_PROC, _SERVER_TEMP_ROOT

    proc = _SERVER_PROC
    _SERVER_PROC = None
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    if _SERVER_TEMP_ROOT and os.path.isdir(_SERVER_TEMP_ROOT):
        shutil.rmtree(_SERVER_TEMP_ROOT, ignore_errors=True)
    _SERVER_TEMP_ROOT = None


if pytest is not None:
    @pytest.fixture(scope="session", autouse=True)
    def _isolated_api_server():
        _assert_no_external_server_target()
        _start_isolated_test_server()
        try:
            yield
        finally:
            try:
                cleanup()
            except Exception:
                pass
            _stop_isolated_test_server()


# ── Helpers ──────────────────────────────────────────────────

class TestFailure(Exception):
    pass


# Prevent pytest from trying to collect this helper class as a test.
TestFailure.__test__ = False


def skip_test(reason):
    if pytest is not None and "PYTEST_CURRENT_TEST" in os.environ:
        pytest.skip(reason)
    raise TestFailure(f"SKIP: {reason}")


def require_full_mode():
    if not FULL_MODE:
        skip_test("requires full suite")


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run_test(name, func, requires_full=False):
    if requires_full and not FULL_MODE:
        print(f"  [ SKIP ] {name} (requires --full)")
        results["skipped"] += 1
        return
    try:
        func()
        print(f"  [ PASS ] {name}")
        results["passed"] += 1
    except TestFailure as e:
        msg = str(e)
        if msg.startswith("SKIP:"):
            print(f"  [ SKIP ] {name} ({msg[5:].strip()})")
            results["skipped"] += 1
        else:
            print(f"  [ FAIL ] {name}")
            print(f"           {msg}")
            results["failed"] += 1
            failures.append((name, msg))
    except Exception as e:
        print(f"  [ FAIL ] {name}")
        print(f"           {type(e).__name__}: {e}")
        results["failed"] += 1
        failures.append((name, str(e)))


def assert_status(resp, expected=200, msg=""):
    if resp.status_code != expected:
        body = resp.text[:500]
        raise TestFailure(
            f"Expected {expected}, got {resp.status_code}. {msg}\n"
            f"           Body: {body}"
        )


def assert_key(data, key):
    if key not in data:
        raise TestFailure(f"Missing key '{key}' in: {json.dumps(data)[:300]}")


def wait_for_task(task, timeout=120, poll_interval=2):
    """Poll /api/status/{task} until it stops running or timeout is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/status/{task}", timeout=10)
        if r.status_code == 200 and not r.json().get("running"):
            return True
        time.sleep(poll_interval)
    return False


def wait_for_audio_idle(timeout=120, poll_interval=2):
    """Wait until audio has no running work and no queued jobs."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = get("/api/status/audio")
            if r.status_code == 200:
                data = r.json()
                if (
                    not data.get("running")
                    and not data.get("merge_running")
                    and not data.get("current_job")
                    and not data.get("queue")
                ):
                    return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=30, **kwargs)


def post(path, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=kwargs.pop("timeout", 30), **kwargs)


def delete(path, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", timeout=30, **kwargs)


def _is_local_server():
    try:
        host = (urlparse(BASE_URL).hostname or "").lower()
    except Exception:
        return False
    return host in {"127.0.0.1", "localhost"}


def _cleanup_local_upload_state():
    if not _is_local_server():
        return []
    removed = []
    if os.path.isdir(UPLOADS_PATH):
        for name in os.listdir(UPLOADS_PATH):
            if not name.startswith(TEST_PREFIX):
                continue
            path = os.path.join(UPLOADS_PATH, name)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    removed.append(f"upload {name}")
                except Exception:
                    pass
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            input_path = (state.get("input_file_path") or "").strip()
            if input_path and os.path.basename(input_path).startswith(TEST_PREFIX):
                state.pop("input_file_path", None)
                state["render_prep_complete"] = False
                state.pop("processing_stage_markers", None)
                with open(STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                removed.append("state input_file_path")
    except Exception:
        pass
    return removed

def cleanup():
    print(f"\n--- Cleanup ---")
    items = []

    try:
        post("/api/cancel_audio", json={})
    except Exception:
        pass

    try:
        post("/api/dataset_builder/cancel")
    except Exception:
        pass

    try:
        delete(f"/api/scripts/{TEST_PREFIX}script")
        items.append("test script")
    except Exception:
        pass

    try:
        delete(f"/api/dataset_builder/{TEST_PREFIX}builder_proj")
        items.append("builder project")
    except Exception:
        pass

    try:
        delete(f"/api/dataset_builder/{TEST_PREFIX}gen_proj")
        items.append("gen project")
    except Exception:
        pass

    try:
        r = get("/api/dataset_builder/list")
        if r.status_code == 200:
            for entry in r.json():
                name = entry.get("name", "")
                if name.startswith(TEST_PREFIX):
                    delete(f"/api/dataset_builder/{name}")
                    items.append(f"builder {name}")
    except Exception:
        pass

    try:
        delete(f"/api/lora/datasets/{TEST_PREFIX}dataset")
        items.append("test dataset")
    except Exception:
        pass

    try:
        r = get("/api/voice_design/list")
        if r.status_code == 200:
            for v in r.json():
                if v.get("id", "").startswith(TEST_PREFIX):
                    delete(f"/api/voice_design/{v['id']}")
                    items.append(f"voice {v['id']}")
    except Exception:
        pass

    for removed in _cleanup_local_upload_state():
        items.append(removed)

    if items:
        print(f"  Cleaned: {', '.join(items)}")
    else:
        print(f"  Nothing to clean")


if pytest is not None:
    @pytest.fixture(scope="session", autouse=True)
    def _test_api_session_cleanup():
        cleanup()
        yield
        cleanup()
