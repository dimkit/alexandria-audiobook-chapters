import copy
import importlib.util
import os
import tempfile
import unittest
import asyncio
from fastapi import HTTPException
from fastapi import BackgroundTasks

MODULE_PATH = os.path.join(os.path.dirname(__file__), "app.py")
SPEC = importlib.util.spec_from_file_location("alexandria_app_module_workflow_entrypoints", MODULE_PATH)
app_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(app_module)


def _quiesce_workflows():
    with app_module.processing_workflow_lock:
        app_module.process_state["processing_workflow"]["running"] = False
        app_module.process_state["processing_workflow"]["paused"] = False
        app_module.process_state["processing_workflow"]["pause_requested"] = False
    with app_module.new_mode_workflow_lock:
        app_module.process_state["new_mode_workflow"]["running"] = False
        app_module.process_state["new_mode_workflow"]["paused"] = False
        app_module.process_state["new_mode_workflow"]["pause_requested"] = False

    for stage in ("process_paragraphs", "assign_dialogue", "extract_temperament", "create_script", "voices", "proofread"):
        try:
            app_module._terminate_task_process_if_running(stage)
        except Exception:
            pass


_quiesce_workflows()


class WorkflowEntrypointAccessibilityTests(unittest.TestCase):
    def setUp(self):
        _quiesce_workflows()
        self._patches = {}
        with app_module.new_mode_workflow_lock:
            self._backup_new_mode_workflow = copy.deepcopy(app_module.process_state["new_mode_workflow"])
        with app_module.processing_workflow_lock:
            self._backup_processing_workflow = copy.deepcopy(app_module.process_state["processing_workflow"])
        with app_module.audio_queue_lock:
            self._backup_audio_queue = copy.deepcopy(app_module.audio_queue)
            self._backup_audio_current_job = copy.deepcopy(app_module.audio_current_job)

    def tearDown(self):
        for name, original in self._patches.items():
            setattr(app_module, name, original)
        with app_module.new_mode_workflow_lock:
            app_module.process_state["new_mode_workflow"] = self._backup_new_mode_workflow
        with app_module.processing_workflow_lock:
            app_module.process_state["processing_workflow"] = self._backup_processing_workflow
        with app_module.audio_queue_lock:
            app_module.audio_queue[:] = self._backup_audio_queue
            app_module.audio_current_job = self._backup_audio_current_job

    def _patch(self, name, value):
        if name not in self._patches:
            self._patches[name] = getattr(app_module, name)
        setattr(app_module, name, value)

    def test_legacy_processing_dispatch_entrypoints_are_accessible(self):
        self._patch("_run_processing_script_stage", lambda: True)
        self._patch("_run_processing_review_stage", lambda: True)
        self._patch("_run_processing_sanity_stage", lambda: True)
        self._patch("_run_processing_repair_stage", lambda: True)
        self._patch("_run_processing_voices_stage", lambda: True)
        self._patch("_run_processing_audio_stage", lambda: True)
        self._patch("_processing_workflow_is_pause_requested", lambda: False)

        for stage in ("script", "review", "sanity", "repair", "voices", "audio"):
            app_module._execute_processing_workflow_stage(stage)

    def test_new_mode_stage_entrypoints_are_accessible(self):
        # Keep task tracking deterministic while bypassing heavyweight subprocess work.
        self._patch("_start_task_run", lambda _task_name: "run-1")
        self._patch("run_voice_processing_task", lambda *args, **kwargs: True)
        self._patch("_new_mode_workflow_is_pause_requested", lambda: False)

        # Render-audio stage should short-circuit cleanly when there is no pending work.
        self._patch("_workflow_pending_audio_indices", lambda: [])
        self._patch("_refresh_audio_process_state_locked", lambda *args, **kwargs: None)
        self._patch(
            "_autosave_current_script_for_workflow",
            lambda **kwargs: {"name": "autosave-smoke", "overwrote": False},
        )

        with app_module.new_mode_workflow_lock:
            app_module.process_state["new_mode_workflow"] = app_module._new_mode_workflow_initial_state() | {
                "running": True,
                "options": {"process_voices": True, "generate_audio": True},
            }

        with app_module.audio_queue_lock:
            app_module.audio_queue.clear()
            app_module.audio_current_job = None

        stages = ("process_voices", "render_audio")
        for stage in stages:
            app_module._run_new_mode_workflow_stage(stage)

        # Autosave hooks should resolve and execute without NameError.
        app_module._maybe_autosave_after_new_mode_stage("create_script")
        app_module._maybe_autosave_after_new_mode_stage("process_voices")

    def test_manual_stage_start_is_blocked_while_new_mode_workflow_active(self):
        with app_module.new_mode_workflow_lock:
            app_module.process_state["new_mode_workflow"] = app_module._new_mode_workflow_initial_state() | {
                "running": True,
                "paused": False,
            }

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(app_module.start_create_script(BackgroundTasks()))
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
