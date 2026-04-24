from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_model_download_toast_script_is_bootstrapped_after_utils():
    main_js = (ROOT / "app/static/js/main.js").read_text(encoding="utf-8")

    utils_index = main_js.index("/static/js/legacy/00_utils.js")
    downloads_index = main_js.index("/static/js/legacy/01_model_download_toast.js")
    assert utils_index < downloads_index


def test_model_download_toast_script_renders_progress_retry_and_sse():
    script = (ROOT / "app/static/js/legacy/01_model_download_toast.js").read_text(encoding="utf-8")

    assert "/api/model_downloads/events" in script
    assert "/api/model_downloads/retry/" in script
    assert "Downloading model weights" in script
    assert "Model download failed" in script
    assert "formatModelDownloadBytes" in script
    assert "renderModelDownloadToast" in script
    assert "EventSource" in script


def test_model_download_toast_styles_are_present():
    css = (ROOT / "app/static/css/app.css").read_text(encoding="utf-8")

    assert ".model-download-toast" in css
    assert ".model-download-progress" in css
    assert ".model-download-file-row" in css
