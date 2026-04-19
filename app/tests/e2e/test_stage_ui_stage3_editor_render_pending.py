"""Non-legacy UI E2E stage coverage."""

from ._stage_ui_helpers import *  # noqa: F401,F403

pytestmark = pytest.mark.skipif(
    not _env_true("THREADSPEAK_E2E_RUN_SPLIT_STAGE_UI"),
    reason=(
        "Split Stage-UI tests are disabled by default. "
        "Consolidated Stage-7 flow covers this pipeline end-to-end. "
        "Set THREADSPEAK_E2E_RUN_SPLIT_STAGE_UI=1 to run split stages."
    ),
)

def test_e2e_stage3_editor_render_pending_nonlegacy_ui_only():
    """
    Top-level rule:
    once browser interactions begin, this flow uses UI navigation/actions only.
    """
    with _exclusive_run_lock("stage3_editor_render_pending_nonlegacy_ui_only"):
        fixtures_dir = os.path.join(SOURCE_APP_DIR, "test_fixtures", "e2e_sim")
        script_fixture_path = os.path.join(fixtures_dir, "lmstudio_generate_script_test_book.json")
        voice_fixture_path = os.path.join(fixtures_dir, "lmstudio_voice_profiles_test_book.json")
        qwen_fixture_path = os.path.join(fixtures_dir, "qwen_local_full_e2e_test_book.json")
        book_path = os.path.join(SOURCE_APP_DIR, "test_fixtures", "files", "test_book.epub")

        assert os.path.exists(script_fixture_path), f"Missing fixture: {script_fixture_path}"
        assert os.path.exists(voice_fixture_path), f"Missing fixture: {voice_fixture_path}"
        assert os.path.exists(qwen_fixture_path), f"Missing fixture: {qwen_fixture_path}"
        assert os.path.exists(book_path), f"Missing book fixture: {book_path}"

        script_payload = _read_json(script_fixture_path)
        voice_payload = _read_json(voice_fixture_path)
        script_model = str(((script_payload.get("metadata") or {}).get("model_name") or "").strip())
        voice_model = str(((voice_payload.get("metadata") or {}).get("model_name") or "").strip())
        assert script_model, "Script fixture metadata.model_name is required."
        assert voice_model, "Voice fixture metadata.model_name is required."

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

        console_errors: list[str] = []
        page_errors: list[str] = []
        warnings: list[str] = []
        http_failures: list[str] = []
        expected_speakers = {
            str(item).strip()
            for item in (((voice_payload.get("metadata") or {}).get("speakers")) or [])
            if str(item).strip()
        }
        assert expected_speakers, "Voice fixture metadata.speakers must include at least one speaker."

        with _report_directory("threadspeak_stage3_editor_report_") as report_root:
            script_lm_trace = os.path.join(report_root, "lm-script-trace.jsonl")
            voice_lm_trace = os.path.join(report_root, "lm-voice-trace.jsonl")
            qwen_report = os.path.join(report_root, "qwen-report.json")
            qwen_trace = os.path.join(report_root, "qwen-trace.jsonl")
            env_overrides = {
                "THREADSPEAK_E2E_SIM_ENABLED": "1",
                "THREADSPEAK_E2E_QWEN_FIXTURE": os.path.abspath(qwen_fixture_path),
                "THREADSPEAK_E2E_QWEN_REPORT_PATH": qwen_report,
                "THREADSPEAK_E2E_QWEN_TRACE_PATH": qwen_trace,
                "THREADSPEAK_E2E_SIM_STRICT": "1",
            }

            with LMStudioSimServer(
                script_fixture_path,
                trace_path=script_lm_trace,
                trace_label="stage3-script-lm",
            ) as script_server:
                with LMStudioSimServer(
                    voice_fixture_path,
                    trace_path=voice_lm_trace,
                    trace_label="stage3-voice-lm",
                ) as voice_server:
                    config_patch["llm"]["base_url"] = f"{script_server.base_url}/v1"
                    with _IsolatedServer(config_patch=config_patch, env_overrides=env_overrides) as app_server:
                        with sync_playwright() as playwright:
                            browser = playwright.chromium.launch(headless=True)
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

                                _wait_for_nav_unlocked(page, '.nav-link[data-tab="editor"]', "Editor tab")
                                page.locator('.nav-link[data-tab="editor"]').click()
                                _wait_for_activity(
                                    "Waiting for Editor tab",
                                    lambda: {"visible": bool(page.locator("#editor-tab").is_visible())},
                                    lambda snapshot: bool(snapshot.get("visible")),
                                )

                                page.locator("#editor-chapter-select").select_option("__whole_project__")
                                _wait_for_activity(
                                    "Waiting for Whole Project chunks before render",
                                    lambda: page.evaluate(
                                        """() => {
                                            const rows = Array.from(document.querySelectorAll('#chunks-table-body tr'));
                                            let textRows = 0;
                                            for (const row of rows) {
                                                const textVal = String(row.querySelector('textarea.chunk-text')?.value || '').trim();
                                                if (textVal) textRows += 1;
                                            }
                                            return { rows: rows.length, text_rows: textRows };
                                        }"""
                                    ),
                                    lambda snapshot: int(snapshot.get("text_rows") or 0) > 0,
                                )

                                pre_render_audio = _fetch_task_status(app_server.base_url, "audio")
                                pre_recent_jobs = list((pre_render_audio or {}).get("recent_jobs") or [])
                                baseline_job_id = int(((pre_recent_jobs[0] or {}).get("id") or 0)) if pre_recent_jobs else 0

                                render_pending_button = page.locator("#btn-batch-fast")
                                assert render_pending_button.is_enabled(), "Render Pending button should be enabled before stage-3 run."
                                with page.expect_response(
                                    lambda response: (
                                        response.url.endswith("/api/generate_batch_fast")
                                        and response.request.method == "POST"
                                        and response.status == 200
                                    ),
                                    timeout=10000,
                                ):
                                    render_pending_button.click()

                                _wait_for_editor_audio_completion(app_server.base_url, baseline_job_id=baseline_job_id)

                                # Force a full UI refresh cycle after completion:
                                # navigate away from Editor and back before final assertions.
                                _wait_for_nav_unlocked(page, '.nav-link[data-tab="voices"]', "Voices tab")
                                page.locator('.nav-link[data-tab="voices"]').click()
                                _wait_for_activity(
                                    "Waiting for Voices tab reload",
                                    lambda: {"visible": bool(page.locator("#voices-tab").is_visible())},
                                    lambda snapshot: bool(snapshot.get("visible")),
                                )

                                _wait_for_nav_unlocked(page, '.nav-link[data-tab="editor"]', "Editor tab")
                                page.locator('.nav-link[data-tab="editor"]').click()
                                _wait_for_activity(
                                    "Waiting for Editor tab reload",
                                    lambda: {"visible": bool(page.locator("#editor-tab").is_visible())},
                                    lambda snapshot: bool(snapshot.get("visible")),
                                )

                                page.locator("#editor-chapter-select").select_option("__whole_project__")
                                _wait_for_activity(
                                    "Waiting for Whole Project rows after reload",
                                    lambda: {
                                        "rows": int(
                                            page.evaluate(
                                                "() => document.querySelectorAll('#chunks-table-body tr').length"
                                            )
                                        ),
                                        "text_rows": int(
                                            page.evaluate(
                                                """() => {
                                                    let n = 0;
                                                    for (const row of Array.from(document.querySelectorAll('#chunks-table-body tr'))) {
                                                        const text = String(row.querySelector('textarea.chunk-text')?.value || '').trim();
                                                        if (text) n += 1;
                                                    }
                                                    return n;
                                                }"""
                                            )
                                        ),
                                    },
                                    lambda snapshot: int(snapshot.get("text_rows") or 0) > 0,
                                )

                                words_text = page.locator("#editor-estimate-words").inner_text().strip()
                                words_value = int("".join(ch for ch in words_text if ch.isdigit()) or "0")
                                assert words_value == 0, f"Expected remaining words to be 0, got: {words_text}"
                                errors_text = page.locator("#editor-estimate-errors").inner_text().strip().lower()
                                assert errors_text.startswith("0 clip"), f"Expected 0 errors, got: {errors_text}"

                                page.locator("#editor-chapter-select").select_option("__whole_project__")
                                _wait_for_activity(
                                    "Waiting for Whole Project rows",
                                    lambda: {
                                        "rows": int(
                                            page.evaluate(
                                                "() => document.querySelectorAll('#chunks-table-body tr').length"
                                            )
                                        )
                                    },
                                    lambda snapshot: int(snapshot.get("rows") or 0) > 0,
                                )

                                audio_check = page.evaluate(
                                    """() => {
                                        const rows = Array.from(document.querySelectorAll('#chunks-table-body tr'));
                                        const details = [];
                                        let textRows = 0;
                                        for (const row of rows) {
                                            const text = String(row.querySelector('textarea.chunk-text')?.value || '').trim();
                                            if (!text) continue;
                                            textRows += 1;
                                            const audio = row.querySelector('audio.chunk-audio');
                                            const audioPath = String(audio?.getAttribute('data-audio-path') || '').trim();
                                            const done = row.classList.contains('status-done');
                                            if (!audioPath || !done) {
                                                details.push({
                                                    id: String(row.getAttribute('data-id') || ''),
                                                    has_audio: Boolean(audioPath),
                                                    status_done: done,
                                                });
                                            }
                                        }
                                        return { text_rows: textRows, missing: details };
                                    }"""
                                )
                                assert int(audio_check.get("text_rows") or 0) > 0, "Expected at least one text clip row in Whole Project view."
                                assert not audio_check.get("missing"), f"Rows missing audio or done status: {audio_check.get('missing')}"
                                playback_check = _assert_editor_compact_player_playback(page)
                                assert not bool(playback_check.get("has_error")), (
                                    f"Compact player reported an error: {playback_check}"
                                )
                                assert bool(playback_check.get("preview_src")), (
                                    f"Compact player did not resolve a preview src: {playback_check}"
                                )

                                assert not console_errors, _report_console(console_errors, page_errors, warnings)
                                assert not page_errors, _report_console(console_errors, page_errors, warnings)
                            except Exception as exc:
                                script_logs = ""
                                try:
                                    script_logs = page.locator("#script-logs").inner_text(timeout=2000)
                                except Exception:
                                    script_logs = ""
                                raise AssertionError(
                                    f"Stage-3 editor UI flow failed: {exc}\n"
                                    f"Script logs tail:\n{script_logs[-2000:]}\n"
                                    f"HTTP failures:\n{chr(10).join(http_failures[-20:]) or 'none'}\n"
                                    f"LM script trace tail ({script_lm_trace}):\n{_tail_file(script_lm_trace)}\n"
                                    f"LM voice trace tail ({voice_lm_trace}):\n{_tail_file(voice_lm_trace)}\n"
                                    f"Qwen trace tail ({qwen_trace}):\n{_tail_file(qwen_trace)}\n"
                                    f"Qwen report tail ({qwen_report}):\n{_tail_file(qwen_report)}\n"
                                    f"{_report_console(console_errors, page_errors, warnings)}"
                                ) from exc
                            finally:
                                context.close()
                                browser.close()

                script_server.assert_all_consumed()
                voice_server.assert_all_consumed()

            if os.path.exists(qwen_report):
                report_payload = _read_json(qwen_report)
                pending = dict(report_payload.get("pending") or {})
                allowed_pending = {"generate_voice_clone", "generate_voice_design"}
                disallowed_pending = {
                    key: value
                    for key, value in pending.items()
                    if str(key) not in allowed_pending
                }
                assert not disallowed_pending, f"Unexpected pending Qwen interactions: {disallowed_pending}"
