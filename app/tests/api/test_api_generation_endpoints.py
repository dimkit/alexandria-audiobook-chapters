"""API endpoint tests split by behavior domain."""

from ._common import *  # noqa: F401,F403

def test_generate_script():
    require_full_mode()
    r = post("/api/generate_script")
    if r.status_code == 400:
        raise TestFailure("SKIP: prerequisite not met (no uploaded file or already running)")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "started":
        raise TestFailure(f"Expected status=started, got {data}")

def test_review_script():
    require_full_mode()
    if not shared.get("has_script"):
        raise TestFailure("SKIP: no annotated script loaded")
    r = post("/api/review_script")
    if r.status_code == 400:
        raise TestFailure("SKIP: already running")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "started":
        raise TestFailure(f"Expected status=started, got {data}")

def test_parse_voices():
    require_full_mode()
    r = post("/api/parse_voices")
    if r.status_code == 400:
        raise TestFailure("SKIP: already running")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "started":
        raise TestFailure(f"Expected status=started, got {data}")

def test_generate_chunk():
    require_full_mode()
    if not shared.get("has_chunks"):
        raise TestFailure("SKIP: no chunks available")
    r = post("/api/chunks/0/generate")
    assert_status(r, 200)

def test_generate_batch():
    require_full_mode()
    if not shared.get("has_chunks"):
        skip_test("no chunks available")
    r = post("/api/generate_batch", json={"indices": [0]})
    if r.status_code == 400:
        skip_test("audio generation already running")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") not in ("started", "queued"):
        raise TestFailure(f"Expected status=started|queued, got {data}")
    # Wait for batch to finish so subsequent tests don't conflict
    if not wait_for_task("audio", timeout=120):
        raise TestFailure("generate_batch did not complete within 120s")

def test_generate_batch_scope_request():
    require_full_mode()
    if not shared.get("has_chunks"):
        skip_test("no chunks available")
    chapter = shared.get("chunk0_chapter")
    payload = {"scope_mode": "chapter" if chapter else "project", "chapter": chapter, "regenerate_all": False}
    r = post("/api/generate_batch", json=payload)
    if r.status_code == 400:
        skip_test("audio generation already running or no renderable chunks in scope")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") not in ("started", "queued"):
        raise TestFailure(f"Expected status=started|queued, got {data}")
    if not wait_for_task("audio", timeout=120):
        raise TestFailure("generate_batch scope request did not complete within 120s")

def test_generate_batch_fast():
    require_full_mode()
    if not shared.get("has_chunks"):
        skip_test("no chunks available")
    # Wait for any prior generation to finish
    if not wait_for_task("audio", timeout=120):
        skip_test("prior audio generation did not finish in time")
    r = post("/api/generate_batch_fast", json={"indices": [0]})
    if r.status_code == 400:
        skip_test("audio generation already running")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") not in ("started", "queued"):
        raise TestFailure(f"Expected status=started|queued, got {data}")

def test_cancel_audio():
    """Cancel endpoint works when nothing is running (resets stuck chunks)."""
    r = post("/api/cancel_audio", json={})
    assert_status(r, 200)
    data = r.json()
    if data.get("status") not in ("not_running", "cancelling"):
        raise TestFailure(f"Expected status not_running or cancelling, got {data}")

def test_export_audacity():
    require_full_mode()
    r = post("/api/export_audacity")
    if r.status_code == 400:
        raise TestFailure("SKIP: already running")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "started":
        raise TestFailure(f"Expected status=started, got {data}")

