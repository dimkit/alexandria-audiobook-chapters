import hashlib
import json
import os


CHECKPOINT_VERSION = 1


def atomic_json_write(path, data):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def load_checkpoint(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(path, task, signature, payload):
    document = {
        "version": CHECKPOINT_VERSION,
        "task": task,
        "signature": signature,
        **payload,
    }
    atomic_json_write(path, document)
    return document


def clear_checkpoint(path):
    if os.path.exists(path):
        os.remove(path)


def file_fingerprint(path):
    stat = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def build_signature(payload):
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
