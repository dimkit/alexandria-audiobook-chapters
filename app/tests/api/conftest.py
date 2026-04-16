"""Pytest fixture registration for API test modules."""

import pytest

from . import _common as common


@pytest.fixture(scope="session", autouse=True)
def _isolated_api_server_session():
    common._assert_no_external_server_target()
    common._start_isolated_test_server()
    try:
        yield
    finally:
        try:
            common.cleanup()
        except Exception:
            pass
        common._stop_isolated_test_server()


@pytest.fixture(scope="session", autouse=True)
def _test_api_session_cleanup():
    common.cleanup()
    yield
    common.cleanup()
