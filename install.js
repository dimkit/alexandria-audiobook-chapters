const basePackages = [
  "uv pip uninstall google-genai",
  "uv pip install -r requirements.txt",
]

const DEFAULT_TTS_PROVIDER = "qwen3"

const coreRuntimePackages = [
  "uv pip install fastapi uvicorn pydantic openai python-docx pytest numpy pydub soundfile librosa requests aiofiles python-multipart",
]

const verifyTestEnv = [
  "python -c \"import fastapi, openai, pytest, uvicorn, pydantic, docx, numpy, pydub, soundfile, librosa; print('Dependency check OK')\"",
]

function providerRuntimePackages(platform, arch, provider = DEFAULT_TTS_PROVIDER) {
  if (!["qwen3", "voxcpm2"].includes(provider)) {
    throw new Error(`Unsupported TTS provider during install: ${provider}`)
  }
  if (platform === "win32") {
    if (provider === "voxcpm2") {
      return ["uv pip install voxcpm"]
    }
    return [
      "uv pip install qwen-tts==0.1.1",
      "uv pip install voxcpm",
    ]
  }
  if (platform === "darwin" && arch === "arm64") {
    const packages = [
      "uv pip uninstall qwen-tts",
      "uv pip install mlx-audio==0.4.2",
      "uv pip install sentencepiece tiktoken",
    ]
    if (provider === "voxcpm2" || provider === DEFAULT_TTS_PROVIDER) {
      packages.push("uv pip install voxcpm")
    }
    return packages
  }
  if (provider === "voxcpm2") {
    return ["uv pip install voxcpm"]
  }
  return ["uv pip install qwen-tts==0.1.1"]
}

function providerVerifyCommands(platform, arch, provider = DEFAULT_TTS_PROVIDER) {
  if (platform === "win32" && (provider === "voxcpm2" || provider === DEFAULT_TTS_PROVIDER)) {
    return ["python -c \"from voxcpm import VoxCPM; print('VoxCPM dependency check OK')\""]
  }
  if (platform === "darwin" && arch === "arm64" && (provider === "voxcpm2" || provider === DEFAULT_TTS_PROVIDER)) {
    return ["python -c \"from voxcpm import VoxCPM; print('VoxCPM dependency check OK')\""]
  }
  if (provider === "voxcpm2") {
    return ["python -c \"from voxcpm import VoxCPM; print('VoxCPM dependency check OK')\""]
  }
  return []
}

module.exports = {
  run: [{
    method: "shell.run",
    params: {
      message: "uv cache clean"
    }
  }, {
    when: "{{!which('sox')}}",
    method: "shell.run",
    params: {
      message: "conda install -y -c conda-forge sox"
    }
  }, {
    method: "shell.run",
    params: {
      path: "app",
      message: "python -m venv env"
    }
  }, {
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: "python scripts/bootstrap_runtime_config.py"
    }
  }, {
    when: "{{platform === 'darwin' && arch === 'arm64' && exists('models')}}",
    method: "fs.rm",
    params: {
      path: "models"
    }
  }, {
    when: "{{platform === 'darwin' && arch === 'arm64' && exists('app/models')}}",
    method: "fs.rm",
    params: {
      path: "app/models"
    }
  }, {
    when: "{{platform === 'darwin' && arch === 'arm64'}}",
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: [
        ...basePackages,
        ...coreRuntimePackages,
        ...providerRuntimePackages("darwin", "arm64"),
        ...providerVerifyCommands("darwin", "arm64"),
        ...verifyTestEnv,
      ]
    }
  }, {
    when: "{{platform === 'win32'}}",
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: [
        ...basePackages,
        ...coreRuntimePackages,
        ...providerRuntimePackages("win32", "x64"),
        ...providerVerifyCommands("win32", "x64"),
        ...verifyTestEnv,
      ]
    }
  }, {
    when: "{{platform === 'linux' || (platform === 'darwin' && arch !== 'arm64')}}",
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: [
        ...basePackages,
        ...coreRuntimePackages,
        ...providerRuntimePackages("linux", "x64"),
        ...providerVerifyCommands("linux", "x64"),
        ...verifyTestEnv,
      ]
    }
  }, {
    when: "{{!(platform === 'darwin' && arch === 'arm64')}}",
    method: "script.start",
    params: {
      uri: "torch.js",
      params: {
        path: "app",
        venv: "env",
        flashattention: true
      }
    }
  }, {
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: "python scripts/install_git_hooks.py"
    }
  }, {
    method: "notify",
    params: {
      html: "Installation Complete! Click 'Start' to launch the application."
    }
  }]
}
