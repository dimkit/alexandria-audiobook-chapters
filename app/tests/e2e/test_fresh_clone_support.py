import os
import subprocess
import tempfile
import unittest

from ._stage_ui_helpers import (
    SOURCE_REPO_DIR,
    _clone_repo_git_ref,
    _fresh_clone_install_commands,
)


class FreshCloneSupportTests(unittest.TestCase):
    def test_clone_repo_git_ref_checks_out_head_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_root = os.path.join(temp_dir, "repo")
            checked_out_commit = _clone_repo_git_ref(SOURCE_REPO_DIR, clone_root)
            expected_commit = subprocess.run(
                ["git", "-C", SOURCE_REPO_DIR, "rev-parse", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            actual_commit = subprocess.run(
                ["git", "-C", clone_root, "rev-parse", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            ).stdout.strip()

        self.assertEqual(checked_out_commit, expected_commit)
        self.assertEqual(actual_commit, expected_commit)

    def test_fresh_clone_install_commands_match_platform_family(self):
        linux_commands = _fresh_clone_install_commands("python", host_platform="linux", host_arch="x86_64")
        darwin_commands = _fresh_clone_install_commands("python", host_platform="darwin", host_arch="arm64")

        self.assertIn(["python", "-m", "pip", "install", "qwen-tts==0.1.1"], linux_commands)
        self.assertNotIn(["python", "-m", "pip", "install", "qwen-tts==0.1.1"], darwin_commands)
        self.assertIn(
            ["python", "-m", "pip", "install", "mlx-audio==0.4.2", "sentencepiece", "tiktoken"],
            darwin_commands,
        )


if __name__ == "__main__":
    unittest.main()
