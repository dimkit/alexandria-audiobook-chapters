"""API endpoint tests split by behavior domain."""

from ._common import *  # noqa: F401,F403
from . import _common as common

def test_voice_design_list():
    r = get("/api/voice_design/list")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

def test_voice_design_delete_404():
    r = delete(f"/api/voice_design/{TEST_PREFIX}fake_id")
    assert_status(r, 404)

def test_voice_design_preview():
    require_full_mode()
    r = post("/api/voice_design/preview", json={
        "description": "A clear young male voice with a steady tone",
        "sample_text": "This is a test of voice design.",
    })
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "audio_url")
    shared["preview_file"] = data["audio_url"].split("/")[-1]

def test_voice_design_save_and_delete():
    require_full_mode()
    preview_file = shared.get("preview_file")
    if not preview_file:
        raise TestFailure("SKIP: no preview file from previous test")

    r = post("/api/voice_design/save", json={
        "name": f"{TEST_PREFIX}voice_design",
        "description": "Test voice",
        "sample_text": "Test text",
        "preview_file": preview_file
    })
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "voice_id")
    voice_id = data["voice_id"]

    # Delete it
    r = delete(f"/api/voice_design/{voice_id}")
    assert_status(r, 200)


# ── Section 9b: Clone Voices ────────────────────────────────

def test_clone_voices_list():
    r = get("/api/clone_voices/list")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

def test_clone_voices_upload_bad_format():
    files = {"file": ("test.txt", b"not audio", "text/plain")}
    r = requests.post(f"{common.BASE_URL}/api/clone_voices/upload", files=files)
    assert_status(r, 400)

def test_clone_voices_delete_404():
    r = delete(f"/api/clone_voices/{TEST_PREFIX}fake_id")
    assert_status(r, 404)

def test_clone_voices_upload_and_delete():
    # Create a minimal WAV file (44-byte header + silence)
    import struct
    sample_rate = 16000
    num_samples = 16000  # 1 second
    data_size = num_samples * 2
    wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size)
    wav_bytes = wav_header + b'\x00' * data_size

    files = {"file": (f"{TEST_PREFIX}clone_test.wav", wav_bytes, "audio/wav")}
    r = requests.post(f"{common.BASE_URL}/api/clone_voices/upload", files=files)
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "voice_id")
    assert_key(data, "filename")
    voice_id = data["voice_id"]

    # Verify it appears in list
    r = get("/api/clone_voices/list")
    assert_status(r, 200)
    found = any(v["id"] == voice_id for v in r.json())
    if not found:
        raise TestFailure(f"Uploaded voice {voice_id} not found in list")

    # Delete it
    r = delete(f"/api/clone_voices/{voice_id}")
    assert_status(r, 200)

    # Verify it's gone
    r = get("/api/clone_voices/list")
    found = any(v["id"] == voice_id for v in r.json())
    if found:
        raise TestFailure(f"Deleted voice {voice_id} still in list")


# ── Section 10: LoRA Datasets ───────────────────────────────

def test_lora_list_datasets():
    r = get("/api/lora/datasets")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

def test_lora_delete_dataset_404():
    r = delete(f"/api/lora/datasets/{TEST_PREFIX}fake_ds")
    assert_status(r, 404)

def test_lora_upload_bad_file():
    files = {"file": (f"{TEST_PREFIX}bad.txt", io.BytesIO(b"not a zip"), "text/plain")}
    r = post("/api/lora/upload_dataset", files=files)
    # Should fail — not a valid zip
    if r.status_code < 400:
        raise TestFailure(f"Expected error for non-zip upload, got {r.status_code}")


# ── Section 11: LoRA Models ─────────────────────────────────

def test_lora_list_models():
    r = get("/api/lora/models")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")
    # Verify built-in adapters have 'downloaded' field
    for m in data:
        if m.get("builtin"):
            if "downloaded" not in m:
                raise TestFailure(f"Built-in adapter {m['id']} missing 'downloaded' field")
    shared["lora_models"] = data

def test_lora_download_invalid():
    r = post(f"/api/lora/download/{TEST_PREFIX}fake_adapter", json={})
    if r.status_code < 400:
        raise TestFailure(f"Expected error for invalid adapter, got {r.status_code}")

def test_lora_delete_model_404():
    r = delete(f"/api/lora/models/{TEST_PREFIX}fake_model")
    assert_status(r, 404)

def test_lora_train_bad_dataset():
    r = post("/api/lora/train", json={
        "name": f"{TEST_PREFIX}model",
        "dataset_id": f"{TEST_PREFIX}nonexistent_ds"
    })
    # Should fail — dataset does not exist
    if r.status_code < 400:
        raise TestFailure(f"Expected error for bad dataset, got {r.status_code}")

def test_lora_preview_404():
    r = post(f"/api/lora/preview/{TEST_PREFIX}fake_adapter")
    assert_status(r, 404)

def test_lora_preview():
    require_full_mode()
    models = shared.get("lora_models", [])
    if not models:
        raise TestFailure("SKIP: no LoRA models available")
    adapter = models[0]
    r = post(f"/api/lora/preview/{adapter['id']}", timeout=120)
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "audio_url")


# ── Section 12: Dataset Builder CRUD ────────────────────────

def test_dataset_builder_list():
    r = get("/api/dataset_builder/list")
    assert_status(r, 200)
    data = r.json()
    if not isinstance(data, list):
        raise TestFailure(f"Expected list, got {type(data).__name__}")

def test_dataset_builder_create():
    r = post("/api/dataset_builder/create", json={
        "name": f"{TEST_PREFIX}builder_proj"
    })
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "name")

def test_dataset_builder_update_meta():
    r = post("/api/dataset_builder/update_meta", json={
        "name": f"{TEST_PREFIX}builder_proj",
        "description": "A test voice description",
        "global_seed": "42"
    })
    assert_status(r, 200)

def test_dataset_builder_update_rows():
    r = post("/api/dataset_builder/update_rows", json={
        "name": f"{TEST_PREFIX}builder_proj",
        "rows": [
            {"emotion": "neutral", "text": "Hello world.", "seed": ""},
            {"emotion": "happy", "text": "Great to see you!", "seed": ""}
        ]
    })
    assert_status(r, 200)
    data = r.json()
    if data.get("sample_count") != 2:
        raise TestFailure(f"Expected sample_count=2, got {data.get('sample_count')}")

def test_dataset_builder_status():
    r = get(f"/api/dataset_builder/status/{TEST_PREFIX}builder_proj")
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "description")
    assert_key(data, "samples")
    assert_key(data, "running")
    assert_key(data, "logs")
    if len(data["samples"]) != 2:
        raise TestFailure(f"Expected 2 samples, got {len(data['samples'])}")

def test_dataset_builder_cancel():
    r = post("/api/dataset_builder/cancel")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") not in ("not_running", "cancelling"):
        raise TestFailure(f"Unexpected cancel status: {data}")

def test_dataset_builder_save_no_samples():
    r = post("/api/dataset_builder/save", json={
        "name": f"{TEST_PREFIX}builder_proj",
        "ref_index": 0
    })
    # Should fail — no completed samples
    if r.status_code < 400:
        raise TestFailure(f"Expected error for save with no samples, got {r.status_code}")

def test_dataset_builder_delete():
    r = delete(f"/api/dataset_builder/{TEST_PREFIX}builder_proj")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "deleted":
        raise TestFailure(f"Expected status=deleted, got {data}")

def test_dataset_builder_delete_404():
    r = delete(f"/api/dataset_builder/{TEST_PREFIX}nonexistent")
    assert_status(r, 404)


# ── Section 13: Merge / Export ──────────────────────────────

def test_lora_test_model():
    require_full_mode()
    models = shared.get("lora_models", [])
    if not models:
        raise TestFailure("SKIP: no LoRA models available")
    adapter = models[0]
    r = post("/api/lora/test", json={
        "adapter_id": adapter["id"],
        "text": "This is a test of the LoRA voice.",
        "instruct": "Neutral, even delivery."
    }, timeout=120)
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "audio_url")

def test_lora_generate_dataset():
    require_full_mode()
    r = post("/api/lora/generate_dataset", json={
        "name": f"{TEST_PREFIX}dataset",
        "description": "A clear young male voice",
        "samples": [
            {"emotion": "neutral", "text": "Hello, this is a test sample."},
            {"emotion": "happy", "text": "Great to see you today!"}
        ]
    })
    if r.status_code == 400:
        raise TestFailure("SKIP: already running or bad request")
    assert_status(r, 200)
    data = r.json()
    if data.get("status") != "started":
        raise TestFailure(f"Expected status=started, got {data}")

def test_dataset_builder_generate_sample():
    require_full_mode()
    # Create a temp project for this test
    post("/api/dataset_builder/create", json={"name": f"{TEST_PREFIX}gen_proj"})
    post("/api/dataset_builder/update_rows", json={
        "name": f"{TEST_PREFIX}gen_proj",
        "rows": [{"emotion": "neutral", "text": "Hello world.", "seed": ""}]
    })

    r = post("/api/dataset_builder/generate_sample", json={
        "description": "A clear male voice",
        "text": "Hello world.",
        "dataset_name": f"{TEST_PREFIX}gen_proj",
        "sample_index": 0,
        "seed": -1
    })
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "status")

    # Cleanup
    delete(f"/api/dataset_builder/{TEST_PREFIX}gen_proj")


# ── Run all tests ────────────────────────────────────────────
