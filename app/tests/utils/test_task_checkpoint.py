from task_checkpoint import build_signature, clear_checkpoint, load_checkpoint, save_checkpoint


def test_save_load_and_clear_checkpoint(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    expected = save_checkpoint(
        str(checkpoint_path),
        task="script_generation",
        signature="sig-123",
        payload={"next_chunk_index": 2, "all_entries": [{"speaker": "NARRATOR"}]},
    )

    loaded = load_checkpoint(str(checkpoint_path))

    assert loaded == expected
    clear_checkpoint(str(checkpoint_path))
    assert load_checkpoint(str(checkpoint_path)) is None


def test_build_signature_changes_when_payload_changes():
    left = build_signature({"task": "script_review", "batch_size": 25})
    right = build_signature({"task": "script_review", "batch_size": 26})

    assert left != right
