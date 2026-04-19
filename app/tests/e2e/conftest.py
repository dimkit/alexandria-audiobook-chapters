import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-fresh-clone-e2e",
        action="store_true",
        default=False,
        help="run the opt-in fresh-clone end-to-end flow that boots a git clone of the configured ref (default: HEAD) and overlays local worktree changes by default",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "fresh_clone_e2e: requires --run-fresh-clone-e2e because it clones a git ref into a fresh app env (set THREADSPEAK_E2E_FRESH_CLONE_REF / THREADSPEAK_E2E_FRESH_CLONE_INCLUDE_WORKTREE to override)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-fresh-clone-e2e"):
        return

    skip_marker = pytest.mark.skip(reason="requires --run-fresh-clone-e2e")
    for item in items:
        if "fresh_clone_e2e" in item.keywords:
            item.add_marker(skip_marker)
