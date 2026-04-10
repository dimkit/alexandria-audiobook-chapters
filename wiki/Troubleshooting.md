# Troubleshooting

## Script generation fails

- Check LLM server is running and accessible.
- Verify model name matches what is loaded.
- Try a different model if current one struggles with JSON output.

## Model download fails or is very slow

- TTS models (~3.5 GB each) are downloaded from Hugging Face on first use.
- If downloads are slow or blocked (common in mainland China), set a mirror before launch:
  - `HF_ENDPOINT=https://hf-mirror.com`
  - Or in Pinokio `start.js` env: `env: { HF_ENDPOINT: "https://hf-mirror.com" }`
- If rate-limited, set `HF_TOKEN` from a Hugging Face account.
- Interrupted downloads should resume after restart.

## TTS generation fails

- Check Pinokio terminal logs for model loading errors.
- Ensure sufficient VRAM (16 GB+ recommended for bfloat16).
- In external mode, verify the Gradio TTS server URL is reachable.
- Confirm `voice_config.json` is valid for all speakers.
- For clone voices, verify reference audio exists and transcript text is accurate.

## Slow batch generation

- Enable **Compile Codec** in Setup (warmup cost, then faster steady-state).
- Increase **Parallel Workers** if VRAM allows.
- Use **Batch (Fast)** mode.
- AMD MIOpen warnings are expected and handled automatically.

## Out of memory errors

- Reduce **Max Chars/Batch**.
- Reduce **Parallel Workers**.
- Close other GPU-heavy applications.
- Use `device: cpu` as fallback (slower).

## Broken or tiny MP3 files (428 bytes)

Conda ffmpeg on Windows may be missing `libmp3lame`.

- Install ffmpeg with MP3 support: `conda install -c conda-forge ffmpeg`
- Or remove conda ffmpeg to use system ffmpeg: `conda remove ffmpeg`
- Verify encoder availability: `ffmpeg -encoders 2>/dev/null | grep mp3`

## Audio quality issues

- Use 5-15 second clean reference audio for cloning.
- Avoid reference samples with background noise.
- Try different seeds for custom voices.

## Mojibake characters in output

- Ensure input text is UTF-8 encoded.
- The app applies automatic fixes for common encoding issues, but source encoding still matters.
