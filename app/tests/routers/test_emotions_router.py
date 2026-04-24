import asyncio
import os
import tempfile
import unittest

from fastapi import HTTPException

from api.routers import emotions_router


class _FakeEngine:
    def __init__(self):
        self.calls = []

    def generate_voice(self, text, instruct, speaker, voice_config, output_path):
        self.calls.append(
            {
                "text": text,
                "instruct": instruct,
                "speaker": speaker,
                "voice_config": voice_config,
                "output_path": output_path,
            }
        )
        with open(output_path, "wb") as f:
            f.write(b"fake-audio")
        return True


class _StubProjectManager:
    def __init__(self):
        self.engine = _FakeEngine()
        self.load_chunks_calls = 0
        self.save_chunks_calls = 0
        self.voice_config_load_calls = 0
        self.voice_config_save_calls = 0

    def get_engine(self):
        return self.engine

    def load_chunks(self):
        self.load_chunks_calls += 1
        return [{"uid": "project-chunk", "text": "do not touch"}]

    def save_chunks(self, chunks):
        self.save_chunks_calls += 1

    def _load_voice_config(self):
        self.voice_config_load_calls += 1
        return {"Project Voice": {"type": "custom", "voice": "Ryan"}}

    def _save_voice_config(self, config):
        self.voice_config_save_calls += 1


class EmotionsRouterTests(unittest.TestCase):
    def test_default_state_contains_twenty_seed_prompts(self):
        with tempfile.TemporaryDirectory() as temp_root:
            with _patched_emotions_root(temp_root):
                state = asyncio.run(emotions_router.get_emotions())

        self.assertEqual(state["speaker"], emotions_router.EMOTIONS_TEST_VOICE)
        self.assertEqual(len(state["rows"]), 20)
        self.assertEqual(state["rows"][0]["instruct"], "Overwhelming joy bursting through every breath and syllable.")
        self.assertEqual(state["rows"][-1]["instruct"], "Sacred awe, hushed and trembling before impossible wonder.")
        self.assertTrue(all(row["status"] == "pending" for row in state["rows"]))

    def test_config_save_persists_standalone_state_without_project_voice_config(self):
        stub = _StubProjectManager()
        with tempfile.TemporaryDirectory() as temp_root:
            with _patched_emotions_root(temp_root, project_manager=stub):
                result = asyncio.run(
                    emotions_router.save_emotions_config(
                        emotions_router.EmotionsConfigRequest(
                            text="The same line for every emotion.",
                            voice_config={
                                "type": "custom",
                                "voice": "Serena",
                                "character_style": "clear theatrical delivery",
                            },
                        )
                    )
                )
                state = asyncio.run(emotions_router.get_emotions())

        self.assertEqual(result["status"], "saved")
        self.assertEqual(state["text"], "The same line for every emotion.")
        self.assertEqual(state["voice_config"]["voice"], "Serena")
        self.assertEqual(stub.voice_config_load_calls, 0)
        self.assertEqual(stub.voice_config_save_calls, 0)
        self.assertEqual(stub.load_chunks_calls, 0)
        self.assertEqual(stub.save_chunks_calls, 0)

    def test_render_validates_text_before_starting(self):
        with tempfile.TemporaryDirectory() as temp_root:
            with _patched_emotions_root(temp_root):
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(
                        emotions_router.render_emotions(
                            emotions_router.EmotionsRenderRequest(regenerate_all=False)
                        )
                    )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("text", str(ctx.exception.detail).lower())

    def test_render_single_row_writes_emotions_audio_url_without_project_chunks(self):
        stub = _StubProjectManager()
        with tempfile.TemporaryDirectory() as temp_root:
            with _patched_emotions_root(temp_root, project_manager=stub):
                asyncio.run(
                    emotions_router.save_emotions_config(
                        emotions_router.EmotionsConfigRequest(
                            text="Do you hear the emotion now?",
                            voice_config={"type": "custom", "voice": "Ryan"},
                        )
                    )
                )
                result = asyncio.run(emotions_router.render_emotion_row(0))
                state = asyncio.run(emotions_router.get_emotions())

                audio_path = os.path.join(temp_root, "audio", "emotion_000.wav")
                self.assertTrue(os.path.exists(audio_path))

        self.assertEqual(result["status"], "done")
        self.assertTrue(result["audio_url"].startswith("/emotions_audio/emotion_000.wav?t="))
        self.assertEqual(state["rows"][0]["status"], "done")
        self.assertTrue(state["rows"][0]["audio_url"].startswith("/emotions_audio/emotion_000.wav?t="))
        self.assertEqual(stub.engine.calls[0]["text"], "Do you hear the emotion now?")
        self.assertEqual(stub.engine.calls[0]["instruct"], emotions_router.EMOTION_PROMPTS[0])
        self.assertEqual(stub.engine.calls[0]["speaker"], emotions_router.EMOTIONS_TEST_VOICE)
        self.assertIn(emotions_router.EMOTIONS_TEST_VOICE, stub.engine.calls[0]["voice_config"])
        self.assertEqual(stub.load_chunks_calls, 0)
        self.assertEqual(stub.save_chunks_calls, 0)

    def test_status_and_cancel_are_standalone(self):
        with tempfile.TemporaryDirectory() as temp_root:
            with _patched_emotions_root(temp_root):
                status = asyncio.run(emotions_router.get_emotions_status())
                cancel = asyncio.run(emotions_router.cancel_emotions_render())

        self.assertEqual(status["running"], False)
        self.assertEqual(status["total"], 20)
        self.assertEqual(cancel["status"], "not_running")


class _patched_emotions_root:
    def __init__(self, temp_root, project_manager=None):
        self.temp_root = temp_root
        self.project_manager = project_manager

    def __enter__(self):
        self.original_dir = emotions_router.EMOTIONS_DIR
        self.original_audio_dir = emotions_router.EMOTIONS_AUDIO_DIR
        self.original_state_path = emotions_router.EMOTIONS_STATE_PATH
        self.original_project_manager = emotions_router.project_manager
        self.original_status = dict(emotions_router._render_status)
        self.original_cancel = emotions_router._render_cancel_event.is_set()
        emotions_router.EMOTIONS_DIR = self.temp_root
        emotions_router.EMOTIONS_AUDIO_DIR = os.path.join(self.temp_root, "audio")
        emotions_router.EMOTIONS_STATE_PATH = os.path.join(self.temp_root, "state.json")
        if self.project_manager is not None:
            emotions_router.project_manager = self.project_manager
        emotions_router._render_status.update(
            {
                "running": False,
                "current": None,
                "completed": 0,
                "total": 20,
                "logs": [],
            }
        )
        emotions_router._render_cancel_event.clear()
        return self

    def __exit__(self, exc_type, exc, tb):
        emotions_router.EMOTIONS_DIR = self.original_dir
        emotions_router.EMOTIONS_AUDIO_DIR = self.original_audio_dir
        emotions_router.EMOTIONS_STATE_PATH = self.original_state_path
        emotions_router.project_manager = self.original_project_manager
        emotions_router._render_status.clear()
        emotions_router._render_status.update(self.original_status)
        if self.original_cancel:
            emotions_router._render_cancel_event.set()
        else:
            emotions_router._render_cancel_event.clear()


if __name__ == "__main__":
    unittest.main()
