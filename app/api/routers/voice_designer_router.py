from fastapi import APIRouter
from .. import shared as _shared

globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

router = APIRouter()

def _load_manifest(path):
    """Load a JSON manifest file, returning [] on missing or corrupt file."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            pass
    return []

def _save_manifest(path, manifest):
    """Write a JSON manifest file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _normalize_saved_voice_name(name: str) -> str:
    return project_manager._normalize_speaker_name(name)


def _current_loaded_project_name() -> str:
    state_path = os.path.join(ROOT_DIR, "state.json")
    if not os.path.exists(state_path):
        return ""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, ValueError, OSError):
        return ""
    return str(state.get("loaded_project_name") or "").strip()


def _match_project_prefixed_saved_voice_name(candidate: str, project_name: str, speaker_name: str) -> bool:
    raw_candidate = str(candidate or "").strip()
    raw_project = str(project_name or "").strip()
    raw_speaker = str(speaker_name or "").strip()
    if not raw_candidate or not raw_project or not raw_speaker:
        return False
    normalized_project = _normalize_saved_voice_name(raw_project)
    normalized_speaker = _normalize_saved_voice_name(raw_speaker)
    if not normalized_project or not normalized_speaker:
        return False
    normalized_candidate = _normalize_saved_voice_name(raw_candidate)
    for separator in (".", "_", " "):
        prefix = f"{normalized_project}{separator}"
        if normalized_candidate.startswith(prefix):
            suffix = normalized_candidate[len(prefix):]
            return suffix == normalized_speaker
    return False


def _find_saved_voice_option_for_speaker(speaker: str):
    normalized_speaker = _normalize_saved_voice_name(speaker)
    if not normalized_speaker or normalized_speaker == _normalize_saved_voice_name("NARRATOR"):
        return None
    current_script_title_fn = getattr(project_manager, "_current_script_title", None)
    current_script_title = _normalize_saved_voice_name(
        current_script_title_fn() if callable(current_script_title_fn) else "Project"
    )
    current_project_name = _normalize_saved_voice_name(_current_loaded_project_name())

    def _build_rel_audio(directory_name: str, entry: dict) -> str:
        filename = (entry.get("filename") or "").strip()
        return f"{directory_name}/{filename}" if filename else ""

    def _match_score(entry: dict, fields, *, allow_filename_fallback: bool, allow_project_prefixed_exact_match: bool, project_name: str):
        for priority, field in enumerate(fields):
            raw_candidate = entry.get(field, "")
            candidate = _normalize_saved_voice_name(raw_candidate)
            if candidate and candidate == normalized_speaker:
                return priority
            if allow_project_prefixed_exact_match and _match_project_prefixed_saved_voice_name(raw_candidate, project_name, speaker):
                return priority
        if allow_filename_fallback:
            filename = os.path.splitext(str(entry.get("filename") or "").strip())[0]
            if filename:
                filename_parts = [part for part in re.split(r"[._-]+", filename) if part]
                if filename_parts:
                    trailing = _normalize_saved_voice_name(filename_parts[-1])
                    if trailing and trailing == normalized_speaker:
                        return len(fields)
        if allow_project_prefixed_exact_match:
            filename = os.path.splitext(str(entry.get("filename") or "").strip())[0]
            if _match_project_prefixed_saved_voice_name(filename, project_name, speaker):
                return len(fields)
        return None

    title_candidates = [current_script_title]
    if current_project_name and current_project_name not in title_candidates:
        title_candidates.append(current_project_name)

    best = None

    for title_priority, candidate_title in enumerate(title_candidates):
        allow_filename_fallback = title_priority == 0
        allow_project_prefixed_exact_match = bool(current_project_name) and title_priority > 0

        for entry in _load_manifest(CLONE_VOICES_MANIFEST):
            rel_audio = _build_rel_audio("clone_voices", entry)
            if not rel_audio or not os.path.exists(os.path.join(ROOT_DIR, rel_audio)):
                continue
            entry_script_title = _normalize_saved_voice_name(entry.get("script_title", ""))
            entry_matches_loaded_project_name = allow_project_prefixed_exact_match and (
                _match_project_prefixed_saved_voice_name(entry.get("speaker", ""), current_project_name, speaker)
                or _match_project_prefixed_saved_voice_name(entry.get("name", ""), current_project_name, speaker)
                or _match_project_prefixed_saved_voice_name(
                    os.path.splitext(str(entry.get("filename") or "").strip())[0],
                    current_project_name,
                    speaker,
                )
            )
            if (not entry_script_title or entry_script_title != candidate_title) and not entry_matches_loaded_project_name:
                continue
            score = _match_score(
                entry,
                ("speaker", "name"),
                allow_filename_fallback=allow_filename_fallback,
                allow_project_prefixed_exact_match=allow_project_prefixed_exact_match,
                project_name=current_project_name,
            )
            if score is None:
                continue
            candidate = {
                "type": "clone",
                "ref_audio": rel_audio,
                "ref_text": (entry.get("sample_text") or "").strip(),
                "generated_ref_text": (entry.get("sample_text") or "").strip(),
                "description": (entry.get("description") or "").strip(),
                "source_name": (entry.get("speaker") or entry.get("name") or "").strip(),
                "priority": (title_priority, 0, score),
            }
            if best is None or candidate["priority"] < best["priority"]:
                best = candidate

        for entry in _load_manifest(DESIGNED_VOICES_MANIFEST):
            rel_audio = _build_rel_audio("designed_voices", entry)
            if not rel_audio or not os.path.exists(os.path.join(ROOT_DIR, rel_audio)):
                continue
            entry_script_title = _normalize_saved_voice_name(entry.get("script_title", ""))
            entry_matches_loaded_project_name = allow_project_prefixed_exact_match and (
                _match_project_prefixed_saved_voice_name(entry.get("speaker", ""), current_project_name, speaker)
                or _match_project_prefixed_saved_voice_name(entry.get("name", ""), current_project_name, speaker)
                or _match_project_prefixed_saved_voice_name(
                    os.path.splitext(str(entry.get("filename") or "").strip())[0],
                    current_project_name,
                    speaker,
                )
            )
            if (not entry_script_title or entry_script_title != candidate_title) and not entry_matches_loaded_project_name:
                continue
            score = _match_score(
                entry,
                ("speaker", "name"),
                allow_filename_fallback=allow_filename_fallback,
                allow_project_prefixed_exact_match=allow_project_prefixed_exact_match,
                project_name=current_project_name,
            )
            if score is None:
                continue
            candidate = {
                "type": "clone",
                "ref_audio": rel_audio,
                "ref_text": (entry.get("sample_text") or "").strip(),
                "generated_ref_text": (entry.get("sample_text") or "").strip(),
                "description": (entry.get("description") or "").strip(),
                "source_name": (entry.get("speaker") or entry.get("name") or "").strip(),
                "priority": (title_priority, 1, score),
            }
            if best is None or candidate["priority"] < best["priority"]:
                best = candidate

    if best:
        best.pop("priority", None)
    return best


def _resolve_voice_alias_target(speaker: str, alias: str, known_names):
    normalized_speaker = _normalize_saved_voice_name(speaker)
    if not normalized_speaker:
        return None

    normalized_alias = _normalize_saved_voice_name(alias)
    if not normalized_alias or normalized_alias == normalized_speaker:
        return None

    for name in known_names:
        if _normalize_saved_voice_name(name) == normalized_alias:
            return name
    return None

@router.post("/api/voice_design/preview")
async def voice_design_preview(request: VoiceDesignPreviewRequest):
    """Generate a preview voice from a text description."""
    engine = project_manager.get_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Failed to initialize TTS engine")

    try:
        wav_path, sr = await asyncio.to_thread(
            engine.generate_voice_design,
            description=request.description,
            sample_text=_apply_project_dictionary(request.sample_text),
            language=request.language,
        )
        normalized, normalize_result = await asyncio.to_thread(
            project_manager._normalize_audio_file,
            wav_path,
            _load_export_config(),
            True,
        )
        if not normalized:
            raise RuntimeError(f"Failed to normalize voice design preview: {normalize_result}")
        # Return relative URL for the static mount
        filename = os.path.basename(wav_path)
        return {"status": "ok", "audio_url": f"/designed_voices/previews/{filename}"}
    except Exception as e:
        logger.error(f"Voice design preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/voice_design/save")
async def voice_design_save(request: VoiceDesignSaveRequest):
    """Save a preview voice as a permanent designed voice."""
    previews_dir = os.path.join(DESIGNED_VOICES_DIR, "previews")
    preview_path = os.path.join(previews_dir, request.preview_file)

    if not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail="Preview file not found")

    safe_name = _sanitize_name(request.name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid voice name")

    # Generate unique ID
    voice_id = f"{safe_name}_{int(time.time())}"
    dest_filename = f"{voice_id}.wav"
    dest_path = os.path.join(DESIGNED_VOICES_DIR, dest_filename)

    shutil.copy2(preview_path, dest_path)
    normalized, normalize_result = project_manager._normalize_audio_file(
        dest_path,
        export_config=_load_export_config(),
        allow_short_single_pass=True,
    )
    if not normalized:
        raise HTTPException(status_code=500, detail=f"Failed to normalize saved voice clip: {normalize_result}")

    # Update manifest
    manifest = _load_manifest(DESIGNED_VOICES_MANIFEST)
    manifest.append({
        "id": voice_id,
        "name": request.name,
        "description": request.description,
        "sample_text": request.sample_text,
        "filename": dest_filename,
        "script_title": project_manager._current_script_title(),
    })
    _save_manifest(DESIGNED_VOICES_MANIFEST, manifest)

    logger.info(f"Designed voice saved: '{request.name}' as {dest_filename}")
    return {"status": "saved", "voice_id": voice_id}

@router.get("/api/voice_design/list")
async def voice_design_list():
    """List all saved designed voices."""
    return _load_manifest(DESIGNED_VOICES_MANIFEST)

@router.delete("/api/voice_design/{voice_id}")
async def voice_design_delete(voice_id: str):
    """Delete a saved designed voice."""
    manifest = _load_manifest(DESIGNED_VOICES_MANIFEST)
    entry = next((v for v in manifest if v["id"] == voice_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Voice not found")

    # Delete WAV file
    wav_path = os.path.join(DESIGNED_VOICES_DIR, entry["filename"])
    if os.path.exists(wav_path):
        os.remove(wav_path)

    # Remove from manifest
    manifest = [v for v in manifest if v["id"] != voice_id]
    _save_manifest(DESIGNED_VOICES_MANIFEST, manifest)

    logger.info(f"Designed voice deleted: {voice_id}")
    return {"status": "deleted", "voice_id": voice_id}
