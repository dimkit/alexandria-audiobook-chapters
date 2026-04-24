import os
import tempfile
import unittest

from model_downloads import ModelDownloadManager


class ModelDownloadManagerTests(unittest.TestCase):
    def test_snapshot_cache_hit_does_not_create_toast_state(self):
        manager = ModelDownloadManager(clear_completed_after_seconds=60)
        calls = []

        result = manager.ensure_hf_snapshot(
            "Qwen/example",
            display_name="Qwen Example",
            local_path_resolver=lambda repo_id, required_files=None: "/cache/qwen-example",
            snapshot_download_fn=lambda **kwargs: calls.append(kwargs),
        )

        self.assertEqual(result, "/cache/qwen-example")
        self.assertEqual(calls, [])
        self.assertEqual(manager.snapshot()["downloads"], [])

    def test_file_download_tracks_progress_speed_eta_and_completion(self):
        manager = ModelDownloadManager(clear_completed_after_seconds=60, time_fn=self._fake_clock([100.0, 101.0, 102.0]))

        with tempfile.TemporaryDirectory() as tmpdir:
            cached_path = os.path.join(tmpdir, "cached.bin")
            local_path = os.path.join(tmpdir, "local.bin")
            with open(cached_path, "wb") as handle:
                handle.write(b"weights")

            def fake_hf_download(**kwargs):
                progress = kwargs["tqdm_class"](total=100, desc="model.bin")
                progress.update(40)
                progress.update(60)
                progress.close()
                return cached_path

            result = manager.download_hf_file(
                repo_id="Repo/Model",
                filename="model.bin",
                display_name="Repo Model",
                local_path=local_path,
                hf_hub_download_fn=fake_hf_download,
            )

        self.assertEqual(result, local_path)
        snapshot = manager.snapshot(include_completed=True)
        self.assertEqual(len(snapshot["downloads"]), 1)
        item = snapshot["downloads"][0]
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["display_name"], "Repo Model")
        self.assertEqual(item["downloaded_bytes"], 100)
        self.assertEqual(item["total_bytes"], 100)
        self.assertGreater(item["speed_bps"], 0)
        self.assertEqual(item["eta_seconds"], 0)
        self.assertEqual(item["files"][0]["filename"], "model.bin")

    def test_failed_download_persists_and_retry_reuses_server_side_spec(self):
        attempts = []
        manager = ModelDownloadManager(clear_completed_after_seconds=60)

        def fake_hf_download(**kwargs):
            attempts.append(kwargs["filename"])
            if len(attempts) == 1:
                progress = kwargs["tqdm_class"](total=100, desc="adapter.bin")
                progress.update(25)
                raise RuntimeError("network down")
            return __file__

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, "adapter.bin")
            with self.assertRaises(RuntimeError):
                manager.download_hf_file(
                    repo_id="Repo/Adapters",
                    filename="adapter.bin",
                    display_name="Adapter",
                    local_path=local_path,
                    hf_hub_download_fn=fake_hf_download,
                )

            failed = manager.snapshot()["downloads"][0]
            self.assertEqual(failed["status"], "failed")
            self.assertTrue(failed["retryable"])
            self.assertIn("network down", failed["error"])

            retry_result = manager.retry_download(failed["id"])
            self.assertEqual(retry_result["status"], "completed")
            self.assertTrue(os.path.exists(local_path))

        self.assertEqual(attempts, ["adapter.bin", "adapter.bin"])

    @staticmethod
    def _fake_clock(values):
        iterator = iter(values)
        last = [values[-1]]

        def now():
            try:
                last[0] = next(iterator)
            except StopIteration:
                pass
            return last[0]

        return now


if __name__ == "__main__":
    unittest.main()
