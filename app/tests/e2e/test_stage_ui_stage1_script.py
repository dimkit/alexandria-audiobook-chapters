"""Non-legacy UI E2E stage coverage."""

from ._stage_ui_helpers import *  # noqa: F401,F403

def test_e2e_stage1_script_nonlegacy_ui_only():
    """
    Top-level test rule:
    never bypass UI interactions once browser flow begins.
    """
    fixtures_dir = os.path.join(SOURCE_APP_DIR, "test_fixtures", "e2e_sim")
    fixture_path = os.path.join(fixtures_dir, "lmstudio_generate_script_test_book.json")
    book_path = os.path.join(SOURCE_APP_DIR, "test_fixtures", "files", "test_book.epub")

    assert os.path.exists(fixture_path), f"Missing fixture: {fixture_path}"
    assert os.path.exists(book_path), f"Missing book fixture: {book_path}"

    fixture_payload = _read_json(fixture_path)
    model_name = str(((fixture_payload.get("metadata") or {}).get("model_name") or "").strip() or "qwen/qwen3.5-9b")

    config_patch = {
        "llm": {
            "base_url": "http://127.0.0.1:1/v1",
            "api_key": "local",
            "model_name": model_name,
            "llm_workers": 1,
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

    with LMStudioSimServer(fixture_path) as lm_server:
        config_patch["llm"]["base_url"] = f"{lm_server.base_url}/v1"
        with _IsolatedServer(config_patch=config_patch) as app_server:
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

                page.on("console", _on_console)
                page.on("pageerror", _on_page_error)

                try:
                    _run_stage1_to_voices_tab(
                        page=page,
                        app_base_url=app_server.base_url,
                        book_path=book_path,
                    )

                    assert not console_errors, _report_console(console_errors, page_errors, warnings)
                    assert not page_errors, _report_console(console_errors, page_errors, warnings)
                except PlaywrightTimeoutError as exc:
                    logs_text = ""
                    try:
                        logs_text = page.locator("#script-logs").inner_text(timeout=2000)
                    except Exception:
                        logs_text = ""
                    raise AssertionError(
                        f"Timed out during stage-1 UI flow: {exc}\n"
                        f"Script logs tail:\n{logs_text[-2000:]}\n"
                        f"{_report_console(console_errors, page_errors, warnings)}"
                    ) from exc
                finally:
                    context.close()
                    browser.close()

        lm_server.assert_all_consumed()
