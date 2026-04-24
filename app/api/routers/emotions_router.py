from fastapi import APIRouter
import hashlib
from .. import shared as _shared

globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

router = APIRouter()

EMOTIONS_TEST_VOICE = "EMOTIONS_TEST_VOICE"
EMOTIONS_STATE_PATH = os.path.join(EMOTIONS_DIR, "state.json")

EMOTION_PROMPTS = [
    "Overwhelming joy bursting through every breath and syllable.",
    "Crushing grief barely held together between trembling words.",
    "Explosive rage, sharp and dangerous, every word burning.",
    "Absolute terror, panicked and breathless, expecting immediate doom.",
    "Cold contempt, cruelly amused by someone beneath notice.",
    "Tender love, intimate and glowing, spoken with reverent warmth.",
    "Bitter jealousy, wounded pride twisting every careful phrase.",
    "Giddy excitement, racing thoughts tumbling out almost uncontrollably.",
    "Deep shame, quiet and exposed, struggling to continue.",
    "Triumphant pride, grand and victorious, savoring total success.",
    "Desperate pleading, voice cracking with urgent impossible hope.",
    "Numb shock, hollow and distant, barely processing reality.",
    "Playful mischief, teasing and bright, hiding a wicked secret.",
    "Suffocating anxiety, fragile control collapsing under imagined catastrophe.",
    "Serene peace, slow and luminous, untouched by fear.",
    "Vicious disgust, recoiling from something morally revolting.",
    "Lonely longing, aching softly for something forever absent.",
    "Defiant courage, wounded but unbroken, refusing to surrender.",
    "Hysterical laughter, unstable delight tipping into madness.",
    "Sacred awe, hushed and trembling before impossible wonder.",
]

DEFAULT_EMOTIONS_VOICE_CONFIG = {
    "type": "custom",
    "voice": "Ryan",
    "character_style": "",
    "seed": "-1",
}

_render_lock = threading.RLock()
_render_thread = None
_render_cancel_event = threading.Event()
_render_status = {
    "running": False,
    "current": None,
    "completed": 0,
    "total": len(EMOTION_PROMPTS),
    "logs": [],
}


class EmotionsConfigRequest(BaseModel):
    text: str = ""
    voice_config: Dict[str, object] = {}


class EmotionsRenderRequest(BaseModel):
    regenerate_all: bool = False


def _default_rows():
    return [
        {
            "index": index,
            "instruct": prompt,
            "status": "pending",
            "audio_url": None,
            "fingerprint": "",
            "error": "",
        }
        for index, prompt in enumerate(EMOTION_PROMPTS)
    ]


def _default_state():
    return {
        "text": "",
        "speaker": EMOTIONS_TEST_VOICE,
        "voice_config": dict(DEFAULT_EMOTIONS_VOICE_CONFIG),
        "rows": _default_rows(),
    }


def _normalize_voice_config(voice_config):
    config = dict(voice_config or {})
    voice_type = str(config.get("type") or "custom").strip() or "custom"
    normalized = dict(DEFAULT_EMOTIONS_VOICE_CONFIG)
    normalized.update(config)
    normalized["type"] = voice_type
    normalized["seed"] = str(normalized.get("seed") if normalized.get("seed") is not None else "-1")
    return normalized


def _row_fingerprint(text, prompt, voice_config):
    payload = {
        "text": str(text or "").strip(),
        "instruct": str(prompt or "").strip(),
        "voice_config": _normalize_voice_config(voice_config),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ensure_emotions_dirs():
    os.makedirs(EMOTIONS_DIR, exist_ok=True)
    os.makedirs(EMOTIONS_AUDIO_DIR, exist_ok=True)


def _load_state():
    _ensure_emotions_dirs()
    state = _default_state()
    if os.path.exists(EMOTIONS_STATE_PATH):
        try:
            with open(EMOTIONS_STATE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                state.update({k: v for k, v in loaded.items() if k in {"text", "speaker", "voice_config", "rows"}})
        except Exception:
            state = _default_state()

    state["speaker"] = EMOTIONS_TEST_VOICE
    state["text"] = str(state.get("text") or "")
    state["voice_config"] = _normalize_voice_config(state.get("voice_config") or {})

    existing_rows = state.get("rows") if isinstance(state.get("rows"), list) else []
    merged_rows = []
    for index, prompt in enumerate(EMOTION_PROMPTS):
        existing = existing_rows[index] if index < len(existing_rows) and isinstance(existing_rows[index], dict) else {}
        row = {
            "index": index,
            "instruct": prompt,
            "status": existing.get("status") or "pending",
            "audio_url": existing.get("audio_url"),
            "fingerprint": existing.get("fingerprint") or "",
            "error": existing.get("error") or "",
        }
        current_fp = _row_fingerprint(state["text"], prompt, state["voice_config"])
        if row["status"] == "done" and row["fingerprint"] != current_fp:
            row["status"] = "pending"
            row["audio_url"] = None
            row["error"] = ""
        merged_rows.append(row)
    state["rows"] = merged_rows
    return state


def _save_state(state):
    _ensure_emotions_dirs()
    temp_path = f"{EMOTIONS_STATE_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, EMOTIONS_STATE_PATH)


def _target_indices(state, regenerate_all=False):
    indices = []
    for row in state.get("rows") or []:
        index = int(row.get("index") or 0)
        fingerprint = _row_fingerprint(state.get("text"), row.get("instruct"), state.get("voice_config"))
        if regenerate_all or row.get("status") != "done" or row.get("fingerprint") != fingerprint:
            indices.append(index)
    return indices


def _generate_row_locked(state, index):
    text = str(state.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Emotions text is required before rendering")
    if index < 0 or index >= len(EMOTION_PROMPTS):
        raise HTTPException(status_code=404, detail="Invalid emotion row")

    engine = project_manager.get_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Failed to initialize TTS engine")

    voice_config = _normalize_voice_config(state.get("voice_config") or {})
    runtime_voice_config = {EMOTIONS_TEST_VOICE: voice_config}
    row = state["rows"][index]
    row["status"] = "generating"
    row["error"] = ""
    _save_state(state)

    output_name = f"emotion_{index:03d}.wav"
    output_path = os.path.join(EMOTIONS_AUDIO_DIR, output_name)
    prompt = EMOTION_PROMPTS[index]
    success = engine.generate_voice(text, prompt, EMOTIONS_TEST_VOICE, runtime_voice_config, output_path)
    fingerprint = _row_fingerprint(text, prompt, voice_config)
    if not success:
        row["status"] = "error"
        row["error"] = "TTS generation failed"
        row["audio_url"] = None
        row["fingerprint"] = fingerprint
        _save_state(state)
        raise HTTPException(status_code=500, detail=row["error"])

    row["status"] = "done"
    row["error"] = ""
    row["fingerprint"] = fingerprint
    row["audio_url"] = f"/emotions_audio/{output_name}?t={int(time.time())}"
    _save_state(state)
    return dict(row)


def _run_batch(indices):
    completed = 0
    for index in indices:
        if _render_cancel_event.is_set():
            break
        with _render_lock:
            _render_status["current"] = index
            _render_status["logs"].append(f"Rendering emotion {index + 1}/{len(EMOTION_PROMPTS)}")
        state = _load_state()
        try:
            _generate_row_locked(state, index)
            completed += 1
            with _render_lock:
                _render_status["completed"] = completed
        except HTTPException as exc:
            with _render_lock:
                _render_status["logs"].append(f"Emotion {index + 1} failed: {exc.detail}")
        except Exception as exc:
            with _render_lock:
                _render_status["logs"].append(f"Emotion {index + 1} failed: {exc}")
    with _render_lock:
        _render_status["running"] = False
        _render_status["current"] = None
        _render_status["logs"].append("Cancelled." if _render_cancel_event.is_set() else "Complete.")
        _render_cancel_event.clear()


@router.get("/api/emotions")
async def get_emotions():
    return _load_state()


@router.post("/api/emotions/config")
async def save_emotions_config(request: EmotionsConfigRequest):
    with _render_lock:
        state = _load_state()
        state["text"] = str(request.text or "")
        state["voice_config"] = _normalize_voice_config(request.voice_config)
        for row in state["rows"]:
            fingerprint = _row_fingerprint(state["text"], row["instruct"], state["voice_config"])
            if row.get("fingerprint") != fingerprint:
                row["status"] = "pending"
                row["audio_url"] = None
                row["error"] = ""
        _save_state(state)
    return {"status": "saved"}


@router.post("/api/emotions/render/{index}")
async def render_emotion_row(index: int):
    with _render_lock:
        if _render_status.get("running"):
            raise HTTPException(status_code=409, detail="Emotions render is already running")
        state = _load_state()
        row = _generate_row_locked(state, int(index))
        return row


@router.post("/api/emotions/render")
async def render_emotions(request: EmotionsRenderRequest):
    global _render_thread
    with _render_lock:
        if _render_status.get("running"):
            raise HTTPException(status_code=409, detail="Emotions render is already running")
        state = _load_state()
        if not str(state.get("text") or "").strip():
            raise HTTPException(status_code=400, detail="Emotions text is required before rendering")
        indices = _target_indices(state, regenerate_all=bool(request.regenerate_all))
        if not indices:
            return {"status": "idle", "total": 0}
        if request.regenerate_all:
            for index in indices:
                state["rows"][index]["status"] = "pending"
                state["rows"][index]["audio_url"] = None
                state["rows"][index]["error"] = ""
            _save_state(state)
        _render_cancel_event.clear()
        _render_status.update(
            {
                "running": True,
                "current": None,
                "completed": 0,
                "total": len(indices),
                "logs": [],
            }
        )
        _render_thread = threading.Thread(target=_run_batch, args=(indices,), daemon=True, name="emotions-render")
        _render_thread.start()
    return {"status": "started", "total": len(indices)}


@router.post("/api/emotions/cancel")
async def cancel_emotions_render():
    with _render_lock:
        if not _render_status.get("running"):
            return {"status": "not_running"}
        _render_cancel_event.set()
        return {"status": "cancelling"}


@router.get("/api/emotions/status")
async def get_emotions_status():
    state = _load_state()
    with _render_lock:
        payload = dict(_render_status)
    payload["rows"] = state["rows"]
    payload["done"] = sum(1 for row in state["rows"] if row.get("status") == "done")
    payload["total"] = len(state["rows"])
    return payload
