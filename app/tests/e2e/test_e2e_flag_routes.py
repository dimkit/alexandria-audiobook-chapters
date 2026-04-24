import importlib.util
import os
import unittest


_CONFTST_PATH = os.path.join(os.path.dirname(__file__), "conftest.py")
_SPEC = importlib.util.spec_from_file_location("threadspeak_e2e_conftest", _CONFTST_PATH)
assert _SPEC is not None and _SPEC.loader is not None
e2e_conftest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(e2e_conftest)


class _FakeParser:
    def __init__(self):
        self.options = []

    def addoption(self, *args, **kwargs):
        self.options.append((args, kwargs))


class _FakeConfig:
    def __init__(self, values):
        self._values = dict(values)

    def getoption(self, name):
        return self._values.get(name)


class _FakeItem:
    def __init__(self, *keywords):
        self.keywords = set(keywords)
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)


def _marker_reasons(item):
    return [str(getattr(marker, "kwargs", {}).get("reason") or "") for marker in item.markers]


class E2EFlagRouteTests(unittest.TestCase):
    def test_pytest_addoption_registers_renamed_routes_only(self):
        parser = _FakeParser()

        e2e_conftest.pytest_addoption(parser)

        option_names = [args[0] for args, _kwargs in parser.options]

        self.assertIn(e2e_conftest.CRITICAL_PATH_E2E_FLAG, option_names)
        self.assertIn(e2e_conftest.REAL_GENERATION_BACKEND_E2E_FLAG, option_names)
        self.assertIn(e2e_conftest.REAL_GENERATION_BACKEND_E2E_PARTIAL_FLAG, option_names)
        self.assertNotIn("--run-fresh-clone-e2e", option_names)
        self.assertNotIn("--run-fresh-clone-live-e2e", option_names)
        self.assertNotIn("--run-lmstudio-live-e2e", option_names)
        self.assertNotIn("--run-fresh-clone-live-narrated-e2e", option_names)
        self.assertNotIn("--fresh-clone-live-partial", option_names)

    def test_collection_skips_critical_path_tests_without_new_flag(self):
        item = _FakeItem("fresh_clone_e2e")

        e2e_conftest.pytest_collection_modifyitems(
            _FakeConfig(
                {
                    e2e_conftest.CRITICAL_PATH_E2E_FLAG: False,
                    e2e_conftest.REAL_GENERATION_BACKEND_E2E_FLAG: False,
                }
            ),
            [item],
        )

        self.assertEqual(
            _marker_reasons(item),
            [f"requires {e2e_conftest.CRITICAL_PATH_E2E_FLAG}"],
        )

    def test_collection_unlocks_all_real_backend_markers_with_shared_flag(self):
        items = [
            _FakeItem("fresh_clone_live_e2e"),
            _FakeItem("fresh_clone_live_narrated_e2e"),
            _FakeItem("lmstudio_live_e2e"),
        ]

        e2e_conftest.pytest_collection_modifyitems(
            _FakeConfig(
                {
                    e2e_conftest.CRITICAL_PATH_E2E_FLAG: False,
                    e2e_conftest.REAL_GENERATION_BACKEND_E2E_FLAG: True,
                }
            ),
            items,
        )

        self.assertTrue(all(not item.markers for item in items))


if __name__ == "__main__":
    unittest.main()
