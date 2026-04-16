"""Non-legacy UI E2E stage coverage."""

from ._stage_ui_helpers import *  # noqa: F401,F403

def test_e2e_stage2_voices_nonlegacy_ui_only():
    """
    Top-level rule:
    once browser interactions begin, this flow uses UI navigation/actions only.
    """
    fixtures_dir = os.path.join(SOURCE_APP_DIR, "test_fixtures", "e2e_sim")
    script_fixture_path = os.path.join(fixtures_dir, "lmstudio_generate_script_test_book.json")
    voice_fixture_path = os.path.join(fixtures_dir, "lmstudio_voice_profiles_test_book.json")
    qwen_fixture_path = os.path.join(fixtures_dir, "qwen_local_voice_profiles_test_book.json")
    book_path = os.path.join(SOURCE_APP_DIR, "test_fixtures", "files", "test_book.epub")

    assert os.path.exists(script_fixture_path), f"Missing fixture: {script_fixture_path}"
    assert os.path.exists(voice_fixture_path), f"Missing fixture: {voice_fixture_path}"
    assert os.path.exists(qwen_fixture_path), f"Missing fixture: {qwen_fixture_path}"
    assert os.path.exists(book_path), f"Missing book fixture: {book_path}"

    console_errors: list[str] = []
    page_errors: list[str] = []
    warnings: list[str] = []
    http_failures: list[str] = []
    script_payload = _read_json(script_fixture_path)
    voice_payload = _read_json(voice_fixture_path)
    script_model = str(((script_payload.get("metadata") or {}).get("model_name") or "").strip())
    voice_model = str(((voice_payload.get("metadata") or {}).get("model_name") or "").strip())
    expected_speakers = {
        str(item).strip()
        for item in (((voice_payload.get("metadata") or {}).get("speakers")) or [])
        if str(item).strip()
    }
    assert script_model, "Script fixture metadata.model_name is required."
    assert voice_model, "Voice fixture metadata.model_name is required."
    assert expected_speakers, "Voice fixture metadata.speakers must include at least one speaker."

    config_patch = {
        "llm": {
            "base_url": "http://127.0.0.1:1/v1",
            "api_key": "local",
            "model_name": script_model,
            "llm_workers": 1,
        },
        "tts": {
            "mode": "local",
            "local_backend": "qwen",
            "device": "cpu",
            "language": "English",
            "parallel_workers": 1,
        },
        "generation": {
            "legacy_mode": False,
            "chunk_size": 600,
            "max_tokens": 1024,
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "banned_tokens": [],
            "temperament_words": 150,
        },
    }
    env_overrides = {
        "THREADSPEAK_E2E_SIM_ENABLED": "1",
        "THREADSPEAK_E2E_QWEN_FIXTURE": os.path.abspath(qwen_fixture_path),
        "THREADSPEAK_E2E_SIM_STRICT": "1",
    }

    with LMStudioSimServer(script_fixture_path) as script_server:
        with LMStudioSimServer(voice_fixture_path) as voice_server:
            config_patch["llm"]["base_url"] = f"{script_server.base_url}/v1"
            with _IsolatedServer(config_patch=config_patch, env_overrides=env_overrides) as app_server:
                with sync_playwright() as playwright:
                    try:
                        browser = playwright.chromium.launch(headless=True)
                    except Exception as exc:
                        pytest.skip(f"Playwright browser launch failed: {exc}")
                    context = browser.new_context()
                    page = context.new_page()

                    def _on_console(message):
                        text = str(message.text or "").strip()
                        kind = str(message.type or "").strip().lower()
                        if kind == "error":
                            console_errors.append(text)
                        elif kind == "warning":
                            warnings.append(text)

                    def _on_page_error(err):
                        page_errors.append(str(err))

                    def _on_response(response):
                        try:
                            status = int(response.status)
                        except Exception:
                            status = 0
                        if status >= 400:
                            method = str(getattr(response.request, "method", "") or "")
                            http_failures.append(f"{status} {method} {response.url}")

                    page.on("console", _on_console)
                    page.on("pageerror", _on_page_error)
                    page.on("response", _on_response)

                    try:
                        _run_stage1_to_voices_tab(
                            page=page,
                            app_base_url=app_server.base_url,
                            book_path=book_path,
                        )

                        _switch_llm_via_setup_ui(
                            page,
                            llm_base_url=f"{voice_server.base_url}/v1",
                            llm_model_name=voice_model,
                        )

                        page.locator('.nav-link[data-tab="voices"]').click()
                        _wait_for_activity(
                            "Waiting for Voices tab",
                            lambda: {"visible": bool(page.locator("#voices-tab").is_visible())},
                            lambda snapshot: bool(snapshot.get("visible")),
                        )

                        pre_generation_states = _read_voice_card_states(page)
                        speaker_list = set(pre_generation_states.keys())
                        assert speaker_list == expected_speakers, f"Unexpected speaker rows before generation: {speaker_list}"
                        eligible_speakers = {
                            speaker
                            for speaker, state in pre_generation_states.items()
                            if not bool(state.get("alias_active")) and not bool(state.get("narrator_threshold_active"))
                        }
                        assert eligible_speakers, "No eligible voice cards available for outstanding generation."

                        page.locator("#generate-outstanding-voices-btn").click()
                        _wait_for_voice_generation_completion(page, eligible_speakers)

                        post_generation_states = _read_voice_card_states(page)
                        speaker_list = set(post_generation_states.keys())
                        assert speaker_list == expected_speakers, f"Unexpected speaker rows after generation: {speaker_list}"

                        for speaker in sorted(eligible_speakers):
                            state = post_generation_states.get(speaker) or {}
                            ref_audio = str(state.get("ref_audio") or "").strip()
                            assert ref_audio, f"Missing design ref audio for eligible speaker {speaker}"
                            assert bool(state.get("retry")), f"Expected Retry state for eligible speaker {speaker}: {state}"

                        playable_speakers = [
                            speaker
                            for speaker, state in sorted(post_generation_states.items())
                            if str(state.get("ref_audio") or "").strip()
                        ]
                        assert playable_speakers, "No playable voice previews available after outstanding generation."
                        for speaker in playable_speakers:
                            card_selector = f'.voice-card[data-voice="{speaker}"]'
                            ref_audio = page.locator(f"{card_selector} .design-ref-audio").input_value().strip()
                            page.locator(f"{card_selector} .design-play-btn").click()
                            _wait_for_preview_playback(page, speaker=speaker, ref_audio=ref_audio)

                        assert not console_errors, _report_console(console_errors, page_errors, warnings)
                        assert not page_errors, _report_console(console_errors, page_errors, warnings)
                    except Exception as exc:
                        script_logs = ""
                        try:
                            script_logs = page.locator("#script-logs").inner_text(timeout=2000)
                        except Exception:
                            script_logs = ""
                        raise AssertionError(
                            f"Stage-2 voices UI flow failed: {exc}\n"
                            f"Script logs tail:\n{script_logs[-2000:]}\n"
                            f"HTTP failures:\n{chr(10).join(http_failures[-20:]) or 'none'}\n"
                            f"{_report_console(console_errors, page_errors, warnings)}"
                        ) from exc
                    finally:
                        context.close()
                        browser.close()

            script_server.assert_all_consumed()
            voice_server.assert_all_consumed()
