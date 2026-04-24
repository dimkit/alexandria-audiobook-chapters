import os
import subprocess
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_pinokio_install_wires_windows_voxcpm2_runtime_packages():
    script = textwrap.dedent(
        f"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');
        const code = fs.readFileSync({str(ROOT / "install.js")!r}, 'utf8');
        const context = {{ module: {{ exports: {{}} }} }};
        vm.runInNewContext(code, context);
        const defaultPackages = context.providerRuntimePackages('win32', 'x64');
        assert(defaultPackages.includes('uv pip install qwen-tts==0.1.1'));
        assert(defaultPackages.includes('uv pip install voxcpm'));
        const defaultVerify = context.providerVerifyCommands('win32', 'x64');
        assert(defaultVerify.some((cmd) => cmd.includes('VoxCPM dependency check OK')));
        const voxPackages = Array.from(context.providerRuntimePackages('win32', 'x64', 'voxcpm2'));
        assert.strictEqual(voxPackages.length, 1);
        assert.strictEqual(voxPackages[0], 'uv pip install voxcpm');
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    try:
        completed = subprocess.run(["node", path], capture_output=True, text=True, check=False)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    assert completed.returncode == 0, completed.stdout + completed.stderr
