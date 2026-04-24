import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import soundfile as sf

from tts import TTSEngine

from ._stage_ui_helpers import _exclusive_run_lock


pytestmark = pytest.mark.voxcpm2_live_e2e

MODEL_ID = "openbmb/VoxCPM2"
LIVE_TEST_LOCK_PATH = os.path.join(tempfile.gettempdir(), "threadspeak_voxcpm2_live_audio.lock")

try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - unavailable on Windows
    fcntl = None


@contextmanager
def _single_voxcpm2_live_guard():
    if fcntl is None:
        with _exclusive_run_lock("voxcpm2_live_audio_backend"):
            yield
        return
    handle = open(LIVE_TEST_LOCK_PATH, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.seek(0)
            owner = (handle.read() or "").strip()
            owner_hint = f" lock owner: {owner}" if owner else ""
            raise AssertionError(
                "Refusing to run VoxCPM2 live audio test concurrently. "
                f"Lock file: {LIVE_TEST_LOCK_PATH}.{owner_hint}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "started_at_epoch": int(time.time())}))
        handle.flush()
        os.fsync(handle.fileno())
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _assert_wav(path: str, *, label: str, min_duration_seconds: float = 0.25) -> dict:
    assert os.path.exists(path), f"{label}: missing WAV output at {path}"
    assert os.path.getsize(path) > 1024, f"{label}: WAV output is unexpectedly small"
    info = sf.info(path)
    duration = float(info.frames) / float(info.samplerate or 1)
    assert info.frames > 0, f"{label}: WAV has no frames"
    assert duration >= min_duration_seconds, (
        f"{label}: WAV duration {duration:.3f}s is shorter than {min_duration_seconds:.3f}s"
    )
    return {
        "path": path,
        "bytes": os.path.getsize(path),
        "duration_seconds": duration,
        "sample_rate": int(info.samplerate),
        "frames": int(info.frames),
    }


def _project_config():
    return {
        "tts": {
            "provider": "voxcpm2",
            "mode": "local",
            "device": "auto",
            "parallel_workers": 1,
            "voxcpm_model_id": MODEL_ID,
            "voxcpm_cfg_value": 2.0,
            "voxcpm_inference_timesteps": 4,
            "voxcpm_normalize": False,
            "voxcpm_load_denoiser": False,
            "voxcpm_denoise_reference": False,
            "voxcpm_optimize": False,
        }
    }


def test_live_voxcpm2_design_clone_and_queue_real_backend(monkeypatch, tmp_path):
    pytest.importorskip("voxcpm")
    local_model_path = TTSEngine._resolve_local_model_path(
        MODEL_ID,
        required_files=(
            "model.safetensors",
            ("audiovae.safetensors", "audiovae.pth"),
        ),
    )
    assert local_model_path, (
        f"VoxCPM2 weights are not present in the local Hugging Face cache for {MODEL_ID}. "
        "Download the model before running this live backend test."
    )

    # This test is specifically for local cached weights; do not let a live run
    # silently become a network download.
    monkeypatch.setenv("THREADSPEAK_DISABLE_MODEL_DOWNLOADS", "1")

    with _single_voxcpm2_live_guard():
        project_root = tmp_path / "project"
        clone_dir = project_root / "clone_voices"
        batch_dir = project_root / "batch"
        clone_dir.mkdir(parents=True)
        batch_dir.mkdir(parents=True)

        engine = TTSEngine(_project_config(), project_root=str(project_root))

        design_description = (
            "A warm, expressive audiobook narrator in her thirties, clear mid pitch, "
            "gentle texture, emotionally responsive delivery"
        )
        reference_text = "This reference line establishes a calm, intimate narrator voice for later cloning."
        preview_path, preview_sr = engine.generate_voice_design(
            description=design_description,
            sample_text=reference_text,
            seed=1234,
        )
        design_ref_path = clone_dir / "voxcpm2_designed_reference.wav"
        os.replace(preview_path, design_ref_path)

        outputs = {
            "designed_reference": _assert_wav(str(design_ref_path), label="designed reference"),
        }
        assert int(preview_sr) == outputs["designed_reference"]["sample_rate"]

        voice_config = {
            "NARRATOR": {
                "type": "clone",
                "description": design_description,
                "ref_audio": str(design_ref_path),
                "ref_text": reference_text,
                "generated_ref_text": reference_text,
                "default_style": "measured audiobook narration",
                "seed": 1234,
            }
        }

        emotional_cases = [
            (
                "clone_calm",
                "Calm and reassuring, soft warmth in the voice",
                "The lantern glowed beside the window while the rain softened into a whisper.",
            ),
            (
                "clone_urgent",
                "Urgent and breathless, voice tight with rising fear",
                "The door shook once, then again, and she knew there was no more time.",
            ),
            (
                "clone_somber",
                "Somber and restrained, quiet grief under every word",
                "By morning, the garden path was empty except for the letter folded on the stone.",
            ),
        ]

        for label, guidance, text in emotional_cases:
            out_path = project_root / f"{label}.wav"
            ok = engine.generate_voice(text, guidance, "NARRATOR", voice_config, str(out_path))
            assert ok, f"{label}: VoxCPM2 clone generation returned false"
            outputs[label] = _assert_wav(str(out_path), label=label)

        queue_chunks = [
            {
                "index": "queue_001",
                "speaker": "NARRATOR",
                "text": "First queued line: a quiet discovery under the old staircase.",
                "instruct": "Curious and hushed, careful pacing",
            },
            {
                "index": "queue_002",
                "speaker": "NARRATOR",
                "text": "Second queued line: the answer arrives like a spark in the dark.",
                "instruct": "Bright surprise, quickened energy",
            },
            {
                "index": "queue_003",
                "speaker": "NARRATOR",
                "text": "Third queued line: the room settles into a long, thoughtful silence.",
                "instruct": "Reflective and low, unhurried cadence",
            },
        ]
        batch_results = engine.generate_batch(queue_chunks, voice_config, str(batch_dir))
        assert batch_results["failed"] == [], f"VoxCPM2 queue failures: {batch_results['failed']}"
        assert batch_results["completed"] == ["queue_001", "queue_002", "queue_003"]

        for chunk in queue_chunks:
            output_path = batch_dir / f"temp_batch_{chunk['index']}.wav"
            outputs[chunk["index"]] = _assert_wav(str(output_path), label=chunk["index"])

        manifest_path = project_root / "voxcpm2_live_outputs.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "model_id": MODEL_ID,
                    "local_model_path": local_model_path,
                    "design_description": design_description,
                    "reference_text": reference_text,
                    "emotional_cases": [
                        {"label": label, "guidance": guidance, "text": text}
                        for label, guidance, text in emotional_cases
                    ],
                    "queue_chunks": queue_chunks,
                    "outputs": outputs,
                    "batch_results": batch_results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
