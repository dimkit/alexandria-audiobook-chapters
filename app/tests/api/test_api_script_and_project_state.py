"""API endpoint tests split by behavior domain."""

from ._common import *  # noqa: F401,F403

def test_upload_file():
    require_full_mode()
    content = b"Chapter One\nIt was a dark and stormy night.\nThe end."
    files = {"file": (f"{TEST_PREFIX}upload.txt", io.BytesIO(content), "text/plain")}
    r = post("/api/upload", files=files)
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "filename")
    assert_key(data, "path")
    if data["filename"] != f"{TEST_PREFIX}upload.txt":
        raise TestFailure(f"Unexpected filename: {data['filename']}")


# ── Section 4: Annotated Script ─────────────────────────────

def test_get_annotated_script():
    r = get("/api/annotated_script")
    if r.status_code == 404:
        shared["has_script"] = False
        return  # acceptable — no script loaded
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")
    shared["has_script"] = True


# ── Section 5: Scripts CRUD ─────────────────────────────────

def test_save_script():
    if not shared.get("has_script"):
        skip_test("no annotated script loaded")
    r = post("/api/scripts/save", json={"name": f"{TEST_PREFIX}script"})
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "saved":
        raise TestFailure(f"Expected status=saved, got {data}")

def test_list_scripts():
    r = get("/api/scripts")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")
    if shared.get("has_script"):
        names = [s["name"] for s in data]
        if f"{TEST_PREFIX}script" not in names:
            raise TestFailure(f"Saved script not in list: {names}")

def test_load_script():
    if not shared.get("has_script"):
        skip_test("no annotated script loaded")
    r = post("/api/scripts/load", json={"name": f"{TEST_PREFIX}script"})
    if r.status_code == 409:
        # Script load is blocked by both active and queued audio work.
        # Cancel any stale queue/current job and wait for full idle before retrying.
        post("/api/cancel_audio", json={})
        if wait_for_audio_idle(timeout=120):
            r = post("/api/scripts/load", json={"name": f"{TEST_PREFIX}script"})
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "loaded":
        raise TestFailure(f"Expected status=loaded, got {data}")

def test_delete_script():
    if not shared.get("has_script"):
        skip_test("no annotated script loaded")
    r = delete(f"/api/scripts/{TEST_PREFIX}script")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "deleted":
        raise TestFailure(f"Expected status=deleted, got {data}")

def test_delete_script_404():
    r = delete(f"/api/scripts/{TEST_PREFIX}nonexistent_xyz")
    assert_status(r, 404)


# ── Section 6: Voices ───────────────────────────────────────

def test_status_known_tasks():
    task_names = [
        "script", "voices", "audio", "audacity_export",
        "review", "lora_training", "dataset_gen", "dataset_builder"
    ]
    for name in task_names:
        r = get(f"/api/status/{name}")
        assert_status(r, 200, msg=f"task={name}")
        data = r.json()
        if "running" not in data:
            raise TestFailure(f"Missing 'running' key for task '{name}'")
        if "logs" not in data:
            raise TestFailure(f"Missing 'logs' key for task '{name}'")

def test_status_unknown_task():
    r = get(f"/api/status/{TEST_PREFIX}fake_task")
    assert_status(r, 404)


# ── Section 9: Voice Design ─────────────────────────────────

def test_get_audiobook():
    r = get("/api/audiobook")
    if r.status_code == 404:
        return  # acceptable — no audiobook generated yet
    assert_status(r, 200)

def test_get_audacity_export():
    r = get("/api/export_audacity")
    if r.status_code == 404:
        return  # acceptable — no export generated yet
    assert_status(r, 200)


# ── Section 14: Full Tests — Generation ─────────────────────

