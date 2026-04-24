import asyncio
import unittest

from api.routers import model_downloads_router


class ModelDownloadRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_manager = model_downloads_router.model_download_manager

    def tearDown(self):
        model_downloads_router.model_download_manager = self._original_manager

    async def test_status_returns_manager_snapshot(self):
        model_downloads_router.model_download_manager = _FakeManager()

        payload = await model_downloads_router.model_downloads_status()

        self.assertEqual(payload["downloads"][0]["id"], "download-1")

    async def test_events_stream_initial_snapshot_and_live_event(self):
        manager = _FakeManager()
        model_downloads_router.model_download_manager = manager

        response = await model_downloads_router.model_downloads_events()
        iterator = response.body_iterator

        first = await iterator.__anext__()
        self.assertIn("event: snapshot", first)
        self.assertIn('"download-1"', first)

        manager.publish({"downloads": [{"id": "download-2"}]})
        second = await asyncio.wait_for(iterator.__anext__(), timeout=1.0)
        self.assertIn("event: snapshot", second)
        self.assertIn('"download-2"', second)

        await iterator.aclose()

    async def test_retry_failed_download_returns_retry_result(self):
        manager = _FakeManager()
        model_downloads_router.model_download_manager = manager

        payload = await model_downloads_router.retry_model_download("download-1")

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(manager.retried_ids, ["download-1"])


class _FakeManager:
    def __init__(self):
        self.retried_ids = []
        self._subscribers = []

    def snapshot(self):
        return {"downloads": [{"id": "download-1"}]}

    def subscribe(self):
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return "sub-1", queue

    def unsubscribe(self, subscriber_id):
        return None

    def retry_download(self, download_id):
        self.retried_ids.append(download_id)
        return {"status": "completed", "id": download_id}

    def publish(self, payload):
        for queue in self._subscribers:
            queue.put_nowait(payload)


if __name__ == "__main__":
    unittest.main()
