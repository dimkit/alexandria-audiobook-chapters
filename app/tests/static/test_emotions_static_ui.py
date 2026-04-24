from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_emotions_tab_is_wired_below_projects():
    index_html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    projects_marker = 'data-tab="saved-scripts">Projects'
    emotions_marker = 'data-tab="emotions">Emotions'

    assert emotions_marker in index_html
    assert index_html.index(projects_marker) < index_html.index(emotions_marker)


def test_emotions_fragment_and_script_are_bootstrapped():
    main_js = (ROOT / "app/static/js/main.js").read_text(encoding="utf-8")

    assert "/static/fragments/emotions.html" in main_js
    assert "/static/js/legacy/17_emotions_tab.js" in main_js


def test_emotions_fragment_contains_expected_controls():
    fragment = (ROOT / "app/static/fragments/emotions.html").read_text(encoding="utf-8")

    assert 'id="emotions-tab"' in fragment
    assert 'id="emotions-text"' in fragment
    assert 'id="emotions-voice-card"' in fragment
    assert 'id="emotions-table-body"' in fragment
    assert "emotionsPlaySequence()" in fragment
    assert "emotionsRender(false)" in fragment
    assert "emotionsRender(true)" in fragment


def test_emotions_script_loads_and_renders_standalone_rows():
    script = (ROOT / "app/static/js/legacy/17_emotions_tab.js").read_text(encoding="utf-8")

    assert "/api/emotions" in script
    assert "window.loadEmotions" in script
    assert "function buildEmotionsRowHtml" in script
    assert "EMOTIONS_TEST_VOICE" in script
