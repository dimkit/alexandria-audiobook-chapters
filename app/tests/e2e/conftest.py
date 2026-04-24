import pytest

CRITICAL_PATH_E2E_FLAG = "--critical-path-e2e"
REAL_GENERATION_BACKEND_E2E_FLAG = "--real-generation-backend-e2e"
REAL_GENERATION_BACKEND_E2E_PARTIAL_FLAG = "--real-generation-backend-e2e-partial"


def pytest_addoption(parser):
    parser.addoption(
        CRITICAL_PATH_E2E_FLAG,
        action="store_true",
        default=False,
        help="run the critical-path fresh-clone end-to-end flow that boots a git clone of the configured ref (default: HEAD) and overlays local worktree changes by default",
    )
    parser.addoption(
        REAL_GENERATION_BACKEND_E2E_FLAG,
        action="store_true",
        default=False,
        help="run the opt-in real-generation-backend E2E lanes that hit real local LM Studio and generation backends",
    )
    parser.addoption(
        REAL_GENERATION_BACKEND_E2E_PARTIAL_FLAG,
        action="store_true",
        default=False,
        help="for the real-generation-backend E2E lanes, keep and reuse the last clone root and resume from checkpointed stages",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"fresh_clone_e2e: requires {CRITICAL_PATH_E2E_FLAG} because it clones a git ref into a fresh app env (set THREADSPEAK_E2E_FRESH_CLONE_REF / THREADSPEAK_E2E_FRESH_CLONE_INCLUDE_WORKTREE to override)",
    )
    config.addinivalue_line(
        "markers",
        f"fresh_clone_live_e2e: requires {REAL_GENERATION_BACKEND_E2E_FLAG} because it runs a heavy fresh-clone full-project flow against live local LLM/TTS backends",
    )
    config.addinivalue_line(
        "markers",
        f"lmstudio_live_e2e: requires {REAL_GENERATION_BACKEND_E2E_FLAG} because it hits a real local LM Studio backend",
    )
    config.addinivalue_line(
        "markers",
        f"fresh_clone_live_narrated_e2e: requires {REAL_GENERATION_BACKEND_E2E_FLAG} because it runs a heavy fresh-clone narrated full-project flow against live local LLM/TTS backends",
    )


def pytest_collection_modifyitems(config, items):
    run_fresh_clone = bool(config.getoption(CRITICAL_PATH_E2E_FLAG))
    run_real_generation_backend = bool(config.getoption(REAL_GENERATION_BACKEND_E2E_FLAG))
    fresh_clone_skip = pytest.mark.skip(reason=f"requires {CRITICAL_PATH_E2E_FLAG}")
    fresh_clone_live_skip = pytest.mark.skip(reason=f"requires {REAL_GENERATION_BACKEND_E2E_FLAG}")
    lmstudio_live_skip = pytest.mark.skip(reason=f"requires {REAL_GENERATION_BACKEND_E2E_FLAG}")
    fresh_clone_live_narrated_skip = pytest.mark.skip(reason=f"requires {REAL_GENERATION_BACKEND_E2E_FLAG}")
    for item in items:
        if "fresh_clone_e2e" in item.keywords and not run_fresh_clone:
            item.add_marker(fresh_clone_skip)
        if "fresh_clone_live_e2e" in item.keywords and not run_real_generation_backend:
            item.add_marker(fresh_clone_live_skip)
        if "lmstudio_live_e2e" in item.keywords and not run_real_generation_backend:
            item.add_marker(lmstudio_live_skip)
        if "fresh_clone_live_narrated_e2e" in item.keywords and not run_real_generation_backend:
            item.add_marker(fresh_clone_live_narrated_skip)
