import os
import subprocess
import tempfile
import unittest
from unittest import mock

from ._stage_ui_helpers import (
    SOURCE_REPO_DIR,
    _copy_repo_git_metadata_and_tracked_files,
    _fresh_clone_install_commands,
    _pid_is_alive,
    _reset_repo_copy_to_ref,
)


class FreshCloneSupportTests(unittest.TestCase):
    def test_repo_copy_reset_checks_out_requested_ref(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_root = os.path.join(temp_dir, "repo")
            _copy_repo_git_metadata_and_tracked_files(
                SOURCE_REPO_DIR,
                clone_root,
            )
            checked_out_commit = _reset_repo_copy_to_ref(
                clone_root,
                source_ref="refs/remotes/origin/main",
            )
            expected_commit = subprocess.run(
                ["git", "-C", SOURCE_REPO_DIR, "rev-parse", "refs/remotes/origin/main"],
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

    def test_pid_is_alive_treats_windows_invalid_parameter_as_dead(self):
        error = OSError(87, "The parameter is incorrect")
        error.winerror = 87
        with mock.patch("os.kill", side_effect=error):
            self.assertFalse(_pid_is_alive(10032))


if __name__ == "__main__":
    unittest.main()
