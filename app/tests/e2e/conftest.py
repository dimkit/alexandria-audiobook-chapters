import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-fresh-clone-e2e",
        action="store_true",
        default=False,
        help="run the opt-in fresh-clone end-to-end flow that boots a git clone of the configured ref (default: HEAD) and overlays local worktree changes by default",
    )
    parser.addoption(
        "--run-fresh-clone-live-e2e",
        action="store_true",
        default=False,
        help="run the opt-in heavy fresh-clone live end-to-end flow that uses real local LM Studio and local voice generation",
    )
    parser.addoption(
        "--fresh-clone-live-partial",
        action="store_true",
        default=False,
        help="for the live fresh-clone E2E lane, keep and reuse the last clone root and resume from checkpointed stages",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "fresh_clone_e2e: requires --run-fresh-clone-e2e because it clones a git ref into a fresh app env (set THREADSPEAK_E2E_FRESH_CLONE_REF / THREADSPEAK_E2E_FRESH_CLONE_INCLUDE_WORKTREE to override)",
    )
    config.addinivalue_line(
        "markers",
        "fresh_clone_live_e2e: requires --run-fresh-clone-live-e2e because it runs a heavy fresh-clone full-project flow against live local LLM/TTS backends",
    )


def pytest_collection_modifyitems(config, items):
    run_fresh_clone = bool(config.getoption("--run-fresh-clone-e2e"))
    run_fresh_clone_live = bool(config.getoption("--run-fresh-clone-live-e2e"))
    fresh_clone_skip = pytest.mark.skip(reason="requires --run-fresh-clone-e2e")
    fresh_clone_live_skip = pytest.mark.skip(reason="requires --run-fresh-clone-live-e2e")
    for item in items:
        if "fresh_clone_e2e" in item.keywords and not run_fresh_clone:
            item.add_marker(fresh_clone_skip)
        if "fresh_clone_live_e2e" in item.keywords and not run_fresh_clone_live:
            item.add_marker(fresh_clone_live_skip)
