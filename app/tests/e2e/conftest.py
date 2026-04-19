import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-fresh-clone-e2e",
        action="store_true",
        default=False,
        help="run the opt-in fresh-clone end-to-end flow that boots a git clone of origin/main",
    )
    parser.addoption(
        "--fresh-clone-source",
        action="store",
        default="origin-main",
        choices=("origin-main", "current"),
        help="select the git source for the fresh-clone e2e lane: origin-main or the current local commit",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "fresh_clone_e2e: requires --run-fresh-clone-e2e because it clones origin/main and bootstraps a fresh app env",
    )


@pytest.fixture
def fresh_clone_source_ref(pytestconfig):
    source = pytestconfig.getoption("--fresh-clone-source")
    if source == "current":
        return "HEAD"
    return "refs/remotes/origin/main"


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-fresh-clone-e2e"):
        return

    skip_marker = pytest.mark.skip(reason="requires --run-fresh-clone-e2e")
    for item in items:
        if "fresh_clone_e2e" in item.keywords:
            item.add_marker(skip_marker)
