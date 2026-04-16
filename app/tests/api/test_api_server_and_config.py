"""API endpoint tests split by behavior domain."""

from ._common import *  # noqa: F401,F403
from . import _common as common

def test_server_reachable():
    r = get("/")
    assert_status(r, 200)
    if "text/html" not in r.headers.get("content-type", ""):
        raise TestFailure(f"Expected HTML, got {r.headers.get('content-type')}")


# ── Section 2: Config ───────────────────────────────────────

def test_get_config():
    r = get("/api/config")
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "llm")
    assert_key(data, "tts")
    # current_file is optional when no source file has been selected yet.
    if "current_file" in data and data["current_file"] is not None and not isinstance(data["current_file"], str):
        raise TestFailure(f"current_file must be string or null, got {type(data['current_file']).__name__}")

def test_save_config_roundtrip():
    # Read original
    r = get("/api/config")
    assert_status(r, 200)
    original = r.json()
    shared["original_config"] = original

    # Build test config with modified language
    test_config = {
        "llm": original["llm"],
        "tts": {**original.get("tts", {}), "language": "_test_roundtrip_lang"},
        "prompts": original.get("prompts"),
        "generation": original.get("generation"),
        "proofread": original.get("proofread"),
        "export": original.get("export"),
    }
    test_config["tts"].setdefault("mode", "external")
    test_config["tts"].setdefault("url", "http://127.0.0.1:7860")
    test_config["tts"].setdefault("device", "auto")

    # Save modified
    r = post("/api/config", json=test_config)
    assert_status(r, 200)

    # Read back and verify
    r = get("/api/config")
    assert_status(r, 200)
    readback = r.json()
    if readback.get("tts", {}).get("language") != "_test_roundtrip_lang":
        raise TestFailure("Config round-trip failed: language not persisted")

    # Verify generation section persists
    if original.get("generation") and not readback.get("generation"):
        raise TestFailure("Config round-trip failed: generation section dropped")

    # Verify export normalization settings persist
    if not readback.get("export"):
        raise TestFailure("Config round-trip failed: export section dropped")
    export = readback["export"]
    for key in (
        "trim_clip_silence_enabled",
        "trim_silence_threshold_dbfs",
        "trim_min_silence_len_ms",
        "trim_keep_padding_ms",
        "normalize_enabled",
        "normalize_target_lufs_mono",
        "normalize_target_lufs_stereo",
        "normalize_true_peak_dbtp",
        "normalize_lra",
    ):
        if key not in export:
            raise TestFailure(f"Config round-trip failed: export.{key} missing")

    # Verify review prompts persist through config save
    readback_prompts = readback.get("prompts", {})
    if original.get("prompts", {}).get("review_system_prompt"):
        if not readback_prompts.get("review_system_prompt"):
            raise TestFailure("Config round-trip failed: review_system_prompt dropped")
    if original.get("prompts", {}).get("attribution_system_prompt"):
        if not readback_prompts.get("attribution_system_prompt"):
            raise TestFailure("Config round-trip failed: attribution_system_prompt dropped")
    if original.get("prompts", {}).get("voice_prompt"):
        if not readback_prompts.get("voice_prompt"):
            raise TestFailure("Config round-trip failed: voice_prompt dropped")

    # Restore original
    restore = {
        "llm": original["llm"],
        "tts": original.get("tts", {"mode": "external", "url": "http://127.0.0.1:7860", "device": "auto"}),
        "prompts": original.get("prompts"),
        "generation": original.get("generation"),
        "proofread": original.get("proofread"),
        "export": original.get("export"),
    }
    post("/api/config", json=restore)

def test_save_export_config_roundtrip():
    r = get("/api/config")
    assert_status(r, 200)
    original = r.json()
    export_original = original.get("export") or {}

    patch_payload = {
        "silence_between_speakers_ms": int(export_original.get("silence_between_speakers_ms", 500)),
        "silence_same_speaker_ms": int(export_original.get("silence_same_speaker_ms", 250)),
        "silence_end_of_chapter_ms": int(export_original.get("silence_end_of_chapter_ms", 3000)),
        "silence_paragraph_ms": int(export_original.get("silence_paragraph_ms", 750)),
        "trim_clip_silence_enabled": False,
        "trim_silence_threshold_dbfs": float(export_original.get("trim_silence_threshold_dbfs", -50.0)),
        "trim_min_silence_len_ms": int(export_original.get("trim_min_silence_len_ms", 150)),
        "trim_keep_padding_ms": int(export_original.get("trim_keep_padding_ms", 40)),
        "normalize_enabled": bool(export_original.get("normalize_enabled", True)),
        "normalize_target_lufs_mono": float(export_original.get("normalize_target_lufs_mono", -18.0)),
        "normalize_target_lufs_stereo": float(export_original.get("normalize_target_lufs_stereo", -16.0)),
        "normalize_true_peak_dbtp": float(export_original.get("normalize_true_peak_dbtp", -1.0)),
        "normalize_lra": float(export_original.get("normalize_lra", 11.0)),
    }

    r = post("/api/config/export", json=patch_payload)
    assert_status(r, 200)
    body = r.json()
    if body.get("status") != "saved":
        raise TestFailure("Export config patch did not report success")

    r = get("/api/config")
    assert_status(r, 200)
    readback = r.json()
    if readback.get("export", {}).get("trim_clip_silence_enabled") is not False:
        raise TestFailure("Export config patch did not persist trim_clip_silence_enabled=false")
    if readback.get("export", {}).get("trim_keep_padding_ms") != patch_payload["trim_keep_padding_ms"]:
        raise TestFailure("Export config patch did not persist trim_keep_padding_ms")

    zero_padding_payload = dict(patch_payload)
    zero_padding_payload["trim_keep_padding_ms"] = 0
    r = post("/api/config/export", json=zero_padding_payload)
    assert_status(r, 200)

    r = get("/api/config")
    assert_status(r, 200)
    zero_readback = r.json()
    if zero_readback.get("export", {}).get("trim_keep_padding_ms") != 0:
        raise TestFailure("Export config patch did not preserve trim_keep_padding_ms=0")

    post("/api/config", json=original)

def test_save_review_prompts_roundtrip():
    # Read current config
    r = get("/api/config")
    assert_status(r, 200)
    original = r.json()

    # Save config with custom review prompts
    test_config = {
        "llm": original["llm"],
        "tts": original.get("tts", {"mode": "local", "url": "http://127.0.0.1:7860", "device": "auto"}),
        "prompts": {
            **(original.get("prompts") or {}),
            "review_system_prompt": f"{TEST_PREFIX}review_sys",
            "review_user_prompt": f"{TEST_PREFIX}review_usr",
        },
        "generation": original.get("generation"),
    }
    r = post("/api/config", json=test_config)
    assert_status(r, 200)

    # Read back and verify
    r = get("/api/config")
    assert_status(r, 200)
    readback = r.json()
    prompts = readback.get("prompts", {})
    if prompts.get("review_system_prompt") != f"{TEST_PREFIX}review_sys":
        raise TestFailure(f"review_system_prompt not persisted: {prompts.get('review_system_prompt')}")
    if prompts.get("review_user_prompt") != f"{TEST_PREFIX}review_usr":
        raise TestFailure(f"review_user_prompt not persisted: {prompts.get('review_user_prompt')}")

    # Restore original
    restore = {
        "llm": original["llm"],
        "tts": original.get("tts", {"mode": "local", "url": "http://127.0.0.1:7860", "device": "auto"}),
        "prompts": original.get("prompts"),
        "generation": original.get("generation"),
    }
    post("/api/config", json=restore)

def test_save_attribution_prompts_roundtrip():
    r = get("/api/config")
    assert_status(r, 200)
    original = r.json()

    test_config = {
        "llm": original["llm"],
        "tts": original.get("tts", {"mode": "local", "url": "http://127.0.0.1:7860", "device": "auto"}),
        "prompts": {
            **(original.get("prompts") or {}),
            "attribution_system_prompt": f"{TEST_PREFIX}attr_sys",
            "attribution_user_prompt": f"{TEST_PREFIX}attr_usr",
        },
        "generation": original.get("generation"),
    }
    r = post("/api/config", json=test_config)
    assert_status(r, 200)

    r = get("/api/config")
    assert_status(r, 200)
    readback = r.json()
    prompts = readback.get("prompts", {})
    if prompts.get("attribution_system_prompt") != f"{TEST_PREFIX}attr_sys":
        raise TestFailure(f"attribution_system_prompt not persisted: {prompts.get('attribution_system_prompt')}")
    if prompts.get("attribution_user_prompt") != f"{TEST_PREFIX}attr_usr":
        raise TestFailure(f"attribution_user_prompt not persisted: {prompts.get('attribution_user_prompt')}")

    restore = {
        "llm": original["llm"],
        "tts": original.get("tts", {"mode": "local", "url": "http://127.0.0.1:7860", "device": "auto"}),
        "prompts": original.get("prompts"),
        "generation": original.get("generation"),
    }
    post("/api/config", json=restore)

def test_get_default_prompts():
    r = get("/api/default_prompts")
    assert_status(r, 200)
    data = r.json()
    assert_key(data, "system_prompt")
    assert_key(data, "user_prompt")
    if not data["system_prompt"]:
        raise TestFailure("system_prompt is empty")
    assert_key(data, "review_system_prompt")
    assert_key(data, "review_user_prompt")
    assert_key(data, "attribution_system_prompt")
    assert_key(data, "attribution_user_prompt")
    assert_key(data, "voice_prompt")
    if not data["review_system_prompt"]:
        raise TestFailure("review_system_prompt is empty")
    if not data["review_user_prompt"]:
        raise TestFailure("review_user_prompt is empty")
    if not data["attribution_system_prompt"]:
        raise TestFailure("attribution_system_prompt is empty")
    if not data["attribution_user_prompt"]:
        raise TestFailure("attribution_user_prompt is empty")
    if not data["voice_prompt"]:
        raise TestFailure("voice_prompt is empty")

def test_get_config_persists_missing_voice_prompt_default():
    config_path = os.path.join(common.ACTIVE_APP_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        original_raw = f.read()
    original = json.loads(original_raw)

    modified = json.loads(original_raw)
    prompts = modified.setdefault("prompts", {})
    prompts.pop("voice_prompt", None)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(modified, f, indent=2, ensure_ascii=False)

    try:
        r = get("/api/config")
        assert_status(r, 200)
        data = r.json()
        if not data.get("prompts", {}).get("voice_prompt"):
            raise TestFailure("GET /api/config did not return voice_prompt")

        with open(config_path, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        if not persisted.get("prompts", {}).get("voice_prompt"):
            raise TestFailure("GET /api/config did not persist backfilled voice_prompt")
    finally:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(original_raw)

def test_get_config_persists_missing_temperament_words_default():
    config_path = os.path.join(common.ACTIVE_APP_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        original_raw = f.read()

    modified = json.loads(original_raw)
    generation = modified.setdefault("generation", {})
    generation.pop("temperament_words", None)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(modified, f, indent=2, ensure_ascii=False)

    try:
        r = get("/api/config")
        assert_status(r, 200)
        data = r.json()
        if data.get("generation", {}).get("temperament_words") != 150:
            raise TestFailure("GET /api/config did not return generation.temperament_words=150")

        with open(config_path, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        if persisted.get("generation", {}).get("temperament_words") != 150:
            raise TestFailure("GET /api/config did not persist backfilled generation.temperament_words")
    finally:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(original_raw)

def test_save_setup_config_roundtrip_temperament_words():
    r = get("/api/config")
    assert_status(r, 200)
    original = r.json()

    payload = {
        "generation": {
            "temperament_words": 222,
        }
    }
    r = post("/api/config/setup", json=payload)
    assert_status(r, 200)

    try:
        r = get("/api/config")
        assert_status(r, 200)
        readback = r.json()
        if readback.get("generation", {}).get("temperament_words") != 222:
            raise TestFailure("POST /api/config/setup did not persist generation.temperament_words")
    finally:
        post("/api/config", json=original)


# ── Section 3: Upload ───────────────────────────────────────
