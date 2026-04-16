"""API endpoint tests split by behavior domain."""

from ._common import *  # noqa: F401,F403
from . import _common as common

def test_get_voices():
    r = get("/api/voices")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

def test_get_voices_reflects_chunk_store_speaker_updates():
    if common.ACTIVE_APP_DIR != common.APP_DIR:
        skip_test("covered by router-level in-process test; isolated API server does not observe out-of-process chunk-store writes")

    project_module_path = os.path.join(common.ACTIVE_APP_DIR, "project.py")
    spec = importlib.util.spec_from_file_location("threadspeak_test_api_project_module", project_module_path)
    if spec is None or spec.loader is None:
        raise TestFailure(f"Unable to load isolated project module from {project_module_path}")
    project_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(project_module)

    layout = RuntimeLayout.from_app_dir(common.ACTIVE_APP_DIR)
    manager = project_module.ProjectManager(layout.project_dir)
    script_path = layout.script_path
    original_chunks = manager.load_chunks()
    original_script = None
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            original_script = f.read()

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump({
                "entries": [
                    {"speaker": f"{TEST_PREFIX}Original", "text": "Original script speaker line."},
                ],
                "dictionary": [],
            }, f)

        manager.save_chunks([
            {
                "id": 0,
                "uid": f"{TEST_PREFIX}uid-0",
                "speaker": f"{TEST_PREFIX}Edited",
                "text": "Edited chunk speaker line.",
                "instruct": "",
                "chapter": "Chapter 1",
                "status": "pending",
                "audio_path": None,
                "audio_validation": None,
                "auto_regen_count": 0,
            }
        ])

        r = get("/api/voices")
        assert_status(r, 200)
        data = r.json()

        by_name = {item.get("name"): item for item in data if isinstance(item, dict)}
        if f"{TEST_PREFIX}Edited" not in by_name:
            raise TestFailure(f"Expected edited chunk speaker in voices list, got {sorted(by_name.keys())}")
        if f"{TEST_PREFIX}Original" in by_name:
            raise TestFailure("Voices endpoint still reflected annotated_script.json instead of chunk-store state")
        if int(by_name[f"{TEST_PREFIX}Edited"].get("line_count") or 0) != 1:
            raise TestFailure(f"Expected edited speaker line_count=1, got {by_name[f'{TEST_PREFIX}Edited']}")
    finally:
        manager.save_chunks(original_chunks)
        if original_script is None:
            try:
                os.remove(script_path)
            except FileNotFoundError:
                pass
        else:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(original_script)
        manager.shutdown_script_store(flush=True)

def test_save_voice_config():
    r = post("/api/save_voice_config", json={
        f"{TEST_PREFIX}voice": {
            "type": "custom",
            "voice": "Ryan",
            "character_style": "",
            "alias": f"{TEST_PREFIX}alias",
            "seed": "-1"
        }
    })
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "saved":
        raise TestFailure(f"Expected status=saved, got {data}")


# ── Section 7: Chunks ───────────────────────────────────────

def test_get_chunks():
    r = get("/api/chunks")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")
    shared["has_chunks"] = len(data) > 0
    if data:
        shared["chunk0_original"] = {
            "text": data[0].get("text", ""),
            "instruct": data[0].get("instruct", ""),
            "speaker": data[0].get("speaker", ""),
        }
        shared["chunk0_chapter"] = (data[0].get("chapter") or "").strip()

def test_get_chunks_view():
    r = get("/api/chunks/view")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

    if shared.get("has_chunks"):
        if not data:
            raise TestFailure("Expected visible chunk list to be populated")
        chapter = shared.get("chunk0_chapter")
        if chapter:
            r = get("/api/chunks/view", params={"chapter": chapter})
            assert_status(r, 200)
            scoped = r.json()
            if not isinstance(scoped, list):
                raise TestFailure(f"Expected list, got {type(scoped).__name__}")
            if any((chunk.get("chapter") or "").strip() != chapter for chunk in scoped):
                raise TestFailure(f"Chapter-scoped view returned chunks outside {chapter!r}")

def test_get_chunk_chapters():
    r = get("/api/chunks/chapters")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, dict):
        raise TestFailure(f"Expected object, got {type(data).__name__}")
    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        raise TestFailure(f"Expected chapters list, got {type(chapters).__name__}")

def test_get_proofread_view():
    r = get("/api/proofread/view")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, dict):
        raise TestFailure(f"Expected object, got {type(data).__name__}")
    if not isinstance(data.get("chunks"), list):
        raise TestFailure(f"Expected chunks list, got {type(data.get('chunks')).__name__}")
    if not isinstance(data.get("pagination"), dict):
        raise TestFailure(f"Expected pagination object, got {type(data.get('pagination')).__name__}")
    if not isinstance(data.get("stats"), dict):
        raise TestFailure(f"Expected stats object, got {type(data.get('stats')).__name__}")

    chapter = shared.get("chunk0_chapter")
    if chapter:
        scoped = get("/api/proofread/view", params={"chapter": chapter, "page_size": 2000})
        assert_status(scoped, 200)
        scoped_data = scoped.json()
        scoped_chunks = scoped_data.get("chunks") or []
        if any((chunk.get("chapter") or "").strip() != chapter for chunk in scoped_chunks):
            raise TestFailure(f"Proofread view returned rows outside chapter {chapter!r}")

def test_get_next_proofread_failure():
    r = get("/api/proofread/next_failure")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, dict):
        raise TestFailure(f"Expected object, got {type(data).__name__}")
    if "found" not in data:
        raise TestFailure(f"Expected found flag, got keys={sorted(data.keys())}")

def test_get_single_chunk():
    if not shared.get("has_chunks"):
        skip_test("no chunks available")

    r = get("/api/chunks/0")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, dict):
        raise TestFailure(f"Expected object, got {type(data).__name__}")
    if str(data.get("id")) != "0":
        raise TestFailure(f"Expected chunk 0, got {data.get('id')!r}")

def test_get_single_chunk_404():
    r = get("/api/chunks/99999")
    assert_status(r, 404)

def test_get_single_chunk_audio_ref():
    if not shared.get("has_chunks"):
        skip_test("no chunks available")

    r = get("/api/chunks/0/audio")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, dict):
        raise TestFailure(f"Expected object, got {type(data).__name__}")
    if "uid" not in data or "status" not in data or "audio_fingerprint" not in data:
        raise TestFailure(f"Missing audio ref keys: {data}")

def test_update_chunk():
    if not shared.get("has_chunks"):
        skip_test("no chunks available")

    r = post("/api/chunks/0", json={
        "text": f"{TEST_PREFIX}updated_text",
        "instruct": f"{TEST_PREFIX}instruct"
    })
    assert_status(r, 200)
    data = r.json()
    if data.get("text") != f"{TEST_PREFIX}updated_text":
        raise TestFailure(f"Chunk text not updated: {data.get('text')}")
    if data.get("audio_path") is not None:
        raise TestFailure(f"Chunk audio was not invalidated: {data.get('audio_path')}")
    if data.get("status") != "pending":
        raise TestFailure(f"Chunk status was not reset: {data.get('status')}")

    # Restore original
    orig = shared.get("chunk0_original", {})
    post("/api/chunks/0", json=orig)

def test_update_chunk_404():
    r = post("/api/chunks/99999", json={"text": "nope"})
    assert_status(r, 404)

def test_insert_chunk():
    if not shared.get("has_chunks"):
        skip_test("no chunks available")

    # Get initial count
    r = get("/api/chunks")
    assert_status(r, 200)
    initial_chunks = r.json()
    initial_count = len(initial_chunks)

    # Insert after index 0
    r = post("/api/chunks/0/insert")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "ok":
        raise TestFailure(f"Expected status=ok, got {data}")
    if data.get("total") != initial_count + 1:
        raise TestFailure(f"Expected total={initial_count + 1}, got {data.get('total')}")

    # Verify the new chunk exists at index 1 with empty text
    r = get("/api/chunks")
    assert_status(r, 200)
    chunks = r.json()
    if len(chunks) != initial_count + 1:
        raise TestFailure(f"Chunk count mismatch: expected {initial_count + 1}, got {len(chunks)}")
    if chunks[1].get("text") != "":
        raise TestFailure(f"Inserted chunk should have empty text, got: {chunks[1].get('text')}")

    # Store index for cleanup in delete test
    shared["inserted_chunk_index"] = 1

def test_insert_chunk_404():
    r = post("/api/chunks/99999/insert")
    assert_status(r, 404)

def test_delete_chunk():
    if not shared.get("has_chunks"):
        skip_test("no chunks available")

    idx = shared.get("inserted_chunk_index")
    if idx is None:
        skip_test("no inserted chunk to delete")

    # Get count before delete
    r = get("/api/chunks")
    assert_status(r, 200)
    before_count = len(r.json())

    r = delete(f"/api/chunks/{idx}")
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "deleted")
    assert_key(data, "total")
    if data["total"] != before_count - 1:
        raise TestFailure(f"Expected total={before_count - 1}, got {data['total']}")

    # Save deleted chunk for restore test
    shared["deleted_chunk"] = data["deleted"]
    shared["deleted_chunk_index"] = idx

def test_delete_chunk_invalid():
    r = delete("/api/chunks/99999")
    assert_status(r, 400)

def test_restore_chunk():
    if not shared.get("deleted_chunk"):
        skip_test("no deleted chunk to restore")

    r = get("/api/chunks")
    assert_status(r, 200)
    before_count = len(r.json())

    r = post("/api/chunks/restore", json={
        "chunk": shared["deleted_chunk"],
        "at_index": shared["deleted_chunk_index"]
    })
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "ok":
        raise TestFailure(f"Expected status=ok, got {data}")
    if data.get("total") != before_count + 1:
        raise TestFailure(f"Expected total={before_count + 1}, got {data.get('total')}")

    # Clean up: delete the restored chunk so we leave chunks as we found them
    delete(f"/api/chunks/{shared['deleted_chunk_index']}")


# ── Section 8: Status Polling ────────────────────────────────
