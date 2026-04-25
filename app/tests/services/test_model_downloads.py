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
                progress = kwargs["tqdm_class"](total=100, desc="model.bin", unit="B")
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
                progress = kwargs["tqdm_class"](total=100, desc="adapter.bin", unit="B")
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

    def test_snapshot_progress_ignores_file_count_tqdm_and_tracks_bytes_only(self):
        manager = ModelDownloadManager(clear_completed_after_seconds=60)

        def fake_snapshot_download(**kwargs):
            with kwargs["tqdm_class"].get_lock():
                pass
            file_counter = kwargs["tqdm_class"](
                ["config.json", "model.safetensors"],
                total=2,
                desc="Fetching 2 files",
            )
            self.assertEqual(list(file_counter), ["config.json", "model.safetensors"])
            file_counter.close()

            byte_counter = kwargs["tqdm_class"](
                total=1024,
                desc="Downloading (incomplete total...)",
                unit="B",
                unit_scale=True,
            )
            byte_counter.update(512)
            byte_counter.close()
            return "/cache/snapshot"

        result = manager.ensure_hf_snapshot(
            "Qwen/example",
            display_name="Qwen Example",
            snapshot_download_fn=fake_snapshot_download,
        )

        self.assertEqual(result, "/cache/snapshot")
        item = manager.snapshot(include_completed=True)["downloads"][0]
        self.assertEqual(item["downloaded_bytes"], 1024)
        self.assertEqual(item["total_bytes"], 1024)
        self.assertEqual(len(item["files"]), 1)
        self.assertNotEqual(item["files"][0]["filename"], "Fetching 2 files")

    def test_progress_updates_are_throttled_to_prevent_event_floods(self):
        now = [100.0]
        manager = ModelDownloadManager(clear_completed_after_seconds=60, time_fn=lambda: now[0])
        _subscriber_id, subscriber_queue = manager.subscribe()

        def fake_hf_download(**kwargs):
            progress = kwargs["tqdm_class"](total=1000, desc="model.bin", unit="B")
            for _ in range(1000):
                progress.update(1)
            progress.close()
            return __file__

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.download_hf_file(
                repo_id="Repo/Model",
                filename="model.bin",
                display_name="Repo Model",
                local_path=os.path.join(tmpdir, "model.bin"),
                hf_hub_download_fn=fake_hf_download,
            )

        self.assertLess(subscriber_queue.qsize(), 12)

    def test_snapshot_missing_required_files_persists_failed_download(self):
        manager = ModelDownloadManager(clear_completed_after_seconds=60)

        with tempfile.TemporaryDirectory() as temp_root:
            snapshot_path = os.path.join(temp_root, "snapshot")
            os.makedirs(snapshot_path, exist_ok=True)
            with open(os.path.join(snapshot_path, "config.json"), "w", encoding="utf-8") as handle:
                handle.write("{}")

            def fake_snapshot_download(**kwargs):
                return snapshot_path

            with self.assertRaisesRegex(RuntimeError, "missing required model files"):
                manager.ensure_hf_snapshot(
                    "mlx-community/example",
                    display_name="MLX Example",
                    required_files=(("*.safetensors", "*.npz"),),
                    snapshot_download_fn=fake_snapshot_download,
                )

        snapshot = manager.snapshot()
        self.assertEqual(len(snapshot["downloads"]), 1)
        self.assertEqual(snapshot["downloads"][0]["status"], "failed")
        self.assertTrue(snapshot["downloads"][0]["retryable"])
        self.assertIn("missing required model files", snapshot["downloads"][0]["error"])

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
