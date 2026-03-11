import copy
import unittest

import app as app_module


class AudioQueueMetricsTests(unittest.TestCase):
    def setUp(self):
        with app_module.audio_queue_lock:
            self._backup_process_audio = copy.deepcopy(app_module.process_state["audio"])
            self._backup_audio_queue = copy.deepcopy(app_module.audio_queue)
            self._backup_audio_current_job = copy.deepcopy(app_module.audio_current_job)

    def tearDown(self):
        with app_module.audio_queue_lock:
            app_module.process_state["audio"] = self._backup_process_audio
            app_module.audio_queue[:] = self._backup_audio_queue
            app_module.audio_current_job = self._backup_audio_current_job

    def test_refresh_preserves_sample_buffer_for_tracker_updates(self):
        with app_module.audio_queue_lock:
            app_module.audio_queue[:] = []
            app_module.audio_current_job = {
                "id": 1,
                "kind": "parallel",
                "status": "running",
                "label": "Test job",
                "scope": "custom",
                "indices": [3],
                "total_chunks": 1,
                "total_words": 6,
                "remaining_words": 6,
                "pending_indices": [3],
                "processed_clips": 0,
                "error_clips": 0,
                "queued_at": 0.0,
                "started_at": 0.0,
                "finished_at": None,
                "last_output_at": None,
            }
            app_module.process_state["audio"]["metrics"] = app_module._new_audio_metrics()
            app_module.process_state["audio"]["heartbeat"] = app_module._new_audio_heartbeat_state()

            # This matches the normal queue refresh path used by /api/status/audio.
            app_module._refresh_audio_process_state_locked(persist=False)

            job = app_module.audio_current_job
            app_module._record_audio_sample_locked(job, 3, 2.0, 6, 6, True)

            metrics = app_module.process_state["audio"]["metrics"]
            self.assertEqual(metrics["processed_clips"], 1)
            self.assertEqual(metrics["successful_clips"], 1)
            self.assertEqual(metrics["error_clips"], 0)
            self.assertEqual(len(metrics["samples"]), 1)
            self.assertEqual(job["pending_indices"], [])
            self.assertEqual(job["remaining_words"], 0)
            self.assertGreater(metrics["words_per_minute"], 0)
            self.assertEqual(metrics["estimated_remaining_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
