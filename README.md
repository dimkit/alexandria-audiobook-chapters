<img width="475" height="467" alt="Alexandria Logo" src="https://github.com/kristopher-miles/threadspeak-audiobook/blob/main/icon.png?raw=true"/>
> This project originated as a fork of [Alexandria Audiobook Generator](https://github.com/Finrandojin/alexandria-audiobook) by Finrandojin. Aduio workflows and tools from that original source are preserved under legacy mode, but are not supported.

# Threadspeak Audiobook Generator

Transform any book or novel into a fully-voiced audiobook using AI-powered script annotation and text-to-speech. Features a built-in Qwen3-TTS engine with batch processing and a browser-based editor for fine-tuning every line before final export.

## Example: [sample.mp3](https://github.com/user-attachments/files/25276110/sample.mp3)

## Features

### AI-Powered Pipeline
- **Local & Cloud LLM Support** - Use any OpenAI-compatible API (LM Studio, Ollama, OpenAI, etc.)
- **Automatic Script Annotation** - LLM parses text into JSON with speakers, dialogue, and TTS instruct directions
- **LLM Script Review** - Optional second LLM pass that fixes common annotation errors: strips attribution tags from dialogue, splits misattributed narration/dialogue, merges over-split narrator entries, and validates instruct fields
- **Smart Chunking** - Groups consecutive lines by speaker (up to 500 chars) for natural flow
- **Context Preservation** - Passes character roster and last 3 script entries between chunks for name and style continuity

### Voice Generation
- **Built-in TTS Engine** - Qwen3-TTS runs locally with no external server required
- **External Server Mode** - Optionally connect to a remote Qwen3-TTS Gradio server
- **Multi-Language Support** - English, Chinese, French, German, Italian, Japanese, Korean, Portuguese, Russian, Spanish, or Auto-detect
- **Custom Voices** - 9 pre-trained voices with instruct-based emotion/tone control
- **Voice Cloning** - Clone any voice from a 5-15 second reference audio sample
- **Voice Designer** - Create new voices from text descriptions (e.g. "A warm, deep male voice with a calm and steady tone")
- **Voice Prompt Suggestion** - Ask the configured LLM to infer a character's base voice description from source paragraphs mentioning that character
- **LoRA Voice Training** - Fine-tune the Base model on custom voice datasets to create persistent voice identities with instruct-following
- **Built-in LoRA Presets** - Pre-trained voice adapters included out of the box, ready to assign to characters
- **Dataset Builder** - Interactive tool for creating LoRA training datasets with per-sample text, emotion, and audio preview
- **Batch Processing** - Generate dozens of chunks simultaneously with 3-6x real-time throughput
- **Codec Compilation** - Optional `torch.compile` optimization for 3-4x faster batch decoding
- **Non-verbal Sounds** - LLM writes natural vocalizations ("Ahh!", "Mmm...", "Haha!") with context-aware instruct directions
- **Natural Pauses** - Intelligent delays between speakers (500ms) and same-speaker segments (250ms)

### Web UI Editor
- **Streamlined Interface** - 5-step core pipeline (Setup, Script, Voices, Editor, Result) plus advanced tools (Designer, Dataset, Training)
- **Chunk Editor** - Edit speaker, text, and instruct for any line
- **Selective Regeneration** - Re-render individual chunks without regenerating everything
- **Batch Processing** - Optimized batch rendering with sub-batching for efficient GPU utilization
- **Live Progress** - Real-time logs and status tracking for all operations
- **Audio Preview** - Play individual chunks or sequence through the entire audiobook
- **Script Library** - Save and load annotated scripts with voice configurations

### Export Options
- **Combined Audiobook** - Single MP3 with all voices and natural pauses
- **Individual Voicelines** - Separate MP3 per line for DAW editing (Audacity, etc.)
- **Audacity Export** - One-click zip with per-speaker WAV tracks, LOF project file, and labels for automatic multi-track import into Audacity
- **M4B Audiobook** - Chaptered M4B (AAC) with per-chunk or auto-detected chapter markers for audiobook players (Audiobookshelf, Apple Books, VLC, etc.)

## Requirements

- [Pinokio](https://pinokio.computer/)
- LLM server (one of the following):
  - [LM Studio](https://lmstudio.ai/) (local) - recommended: Qwen3 or similar
  - [Ollama](https://ollama.ai/) (local)
  - [OpenAI API](https://platform.openai.com/) (cloud)
  - Any OpenAI-compatible API
- **GPU:** 8 GB VRAM minimum, 16 GB+ recommended — see compatibility table below
  - Each TTS model uses ~3.4 GB; remaining VRAM determines batch size
  - CPU mode available on all platforms but significantly slower
- **RAM:** 16 GB recommended (8 GB minimum)
- **Disk:** ~20 GB (8 GB venv/PyTorch, ~7 GB for model weights, working space for audio)

### GPU Compatibility

| GPU | OS | Status | Driver Requirement | Notes |
|-----|-----|--------|-------------------|-------|
| **NVIDIA** | Windows | Full support | Driver 550+ (CUDA 12.8) | Flash attention included for faster encoding |
| **NVIDIA** | Linux | Full support | Driver 550+ (CUDA 12.8) | Flash attention + triton included |
| **AMD** | Linux | Full support | ROCm 6.3 | ROCm optimizations applied automatically |
| **AMD** | Windows | CPU only | N/A | GPU acceleration is not supported — the app runs in CPU mode. For GPU acceleration with AMD, use Linux |
| **Apple Silicon** | macOS | CPU only | N/A | MPS acceleration is not currently supported. Functional but slow |
| **Intel** | macOS | CPU only | N/A | |

> **Note:** No external TTS server is required. Alexandria includes a built-in Qwen3-TTS engine that loads models directly. Model weights are downloaded automatically on first use (~3.5 GB per model variant).

> **Documentation:** For in-depth guidance on voice types, LoRA training, batch generation, and more, see the [Wiki](https://github.com/Finrandojin/alexandria-audiobook/wiki).

## Installation

### Option A: Pinokio (Recommended)

1. Install [Pinokio](https://pinokio.computer/) if you haven't already
2. Open Alexandria on Pinokio: **[Install via Pinokio](https://beta.pinokio.co/apps/github-com-finrandojin-alexandria-audiobook)**
   - Or manually: in Pinokio, click **Download** and paste `https://github.com/Finrandojin/alexandria-audiobook`
3. Click **Install** to set up dependencies
4. Click **Start** to launch the web interface

## First Launch — What to Expect

If this is your first time running Alexandria, read this before anything else.

### 1. You Need an LLM Server Running First

Alexandria does **not** include an LLM — it connects to one over an API. Before generating a script, you must have one of these running:

| Server | Default URL | Install |
|--------|-------------|---------|
| [LM Studio](https://lmstudio.ai/) | `http://localhost:1234/v1` | Download, load a model, start server |
| [Ollama](https://ollama.ai/) | `http://localhost:11434/v1` | `ollama run qwen3` |
| [OpenAI API](https://platform.openai.com/) | `https://api.openai.com/v1` | Get an API key |

If the LLM server isn't running when you click "Generate Script", the generation will fail. Check the Pinokio terminal for error details.

### 2. First TTS Generation Downloads ~3.5 GB

The TTS models are **not** included in the install. They download automatically from Hugging Face the first time you generate audio. This is normal:

- **Each model variant is ~3.5 GB** (CustomVoice, Base/Clone, VoiceDesign)
- Only the variant you use gets downloaded (most users start with CustomVoice)
- Downloads happen in the background — **check the Pinokio terminal** for progress
- The web UI may appear frozen during this time. It is not — it's waiting for the download to finish
- After the first download, models are cached locally and load in seconds

> **Tip:** If the download seems stuck, check your internet connection. If it fails, restart the app and try again — it will resume from where it left off.

### 3. First Batch Has Extra Warmup Time

The very first batch generation in a session takes longer than subsequent ones:

- **MIOpen autotuning** (AMD GPUs): The GPU kernel optimizer runs once per session, adding 30-60 seconds
- **Codec compilation** (if enabled): One-time ~30-60 second warmup, then 3-4x faster for all remaining batches
- **This is expected.** After the first batch, generation speed stabilizes

### 4. VRAM Determines What You Can Do

| Available VRAM | What Works |
|---------------|------------|
| 8 GB | One model at a time, small batches (2-5 chunks), CPU offload may be needed |
| 16 GB | Comfortable for most use cases, batches of 10-20 chunks |
| 24 GB+ | Full speed, batches of 40-60 chunks with codec compilation |

- If you run out of VRAM, reduce **Parallel Workers** or **Max Chars/Batch** in the Setup tab
- Close other GPU applications (games, other AI tools) before generating
- Switching between voice types (Custom → Clone → LoRA) unloads and reloads models, which temporarily frees VRAM

### 5. Where to Look When Something Goes Wrong

The web UI shows high-level status, but **detailed logs are in the Pinokio terminal**:

- Click **Terminal** in the Pinokio sidebar to see real-time output
- Model loading, download progress, VRAM estimates, and errors all appear here
- If generation fails silently in the UI, the terminal will show why

For common issues and solutions, see [Troubleshooting](https://github.com/Finrandojin/alexandria-audiobook/wiki/Troubleshooting).

---

## Quick Start

The interface is split into a **5-step core pipeline** (green tabs, numbered) and **advanced tools** (blue tabs, unnumbered). You only need the core pipeline to produce an audiobook.

### Core Pipeline

**Step 1 — Setup**
Configure your LLM connection and TTS engine. At minimum you need:
- **LLM Base URL**: `http://localhost:1234/v1` (LM Studio) or `http://localhost:11434/v1` (Ollama)
- **LLM API Key**: Your API key (use `local` for local servers)
- **LLM Model Name**: The model to use (e.g., `qwen2.5-14b`)
- **TTS Mode**: `local` (built-in, recommended) — loads models directly, no external server needed
- Click **Save Configuration** when done

**Step 2 — Script**
- Select your book file (.txt or .md) using the file picker — it uploads automatically
- Click **Generate Annotated Script** — this sends the book to your LLM to split it into annotated chunks with speaker labels and voice directions
- *(Optional)* Click **Review Script** if the generated script has issues — this runs a second LLM pass to fix speaker misattributions or formatting problems
- You can save the script for later use with the Save feature below

**Step 3 — Voices**
Each character detected in the script gets a voice card. For each speaker:
- Choose a voice type: Custom Voice (easiest), Clone Voice, LoRA Voice, or Voice Design
- For Custom Voice, pick from 9 presets (Ryan, Serena, Aiden, etc.) and optionally set a character style (e.g., "Heavy Scottish accent")
- For Voice Design, use **Suggest** to generate a base voice description from the uploaded story, or **Create Outstanding Voices** to fill missing descriptions and generate reusable design voices in sequence
- Changes save automatically — see [Voice Types](https://github.com/Finrandojin/alexandria-audiobook/wiki/Voice-Types) for guidance on each type

**Step 4 — Editor**
- Click **Render Pending** to generate audio for all chunks in batch
- Listen to individual chunks or click **Play Sequence** to preview in order
- Edit any chunk's text, speaker, or instruct inline and regenerate it individually
- When satisfied, click **Merge All** to combine everything into the final audiobook

**Step 5 — Result**
- Listen to the finished audiobook in the browser
- Download as MP3, or click **Export to Audacity** for per-speaker WAV tracks

## Web Interface

### Setup Tab
Configure connections to your LLM and TTS engine.

**TTS Settings:**
- **Mode** - `local` (built-in engine) or `external` (connect to Gradio server)
- **Device** - `auto` (recommended), `cuda`, `cpu`, or `mps`
- **Language** - TTS synthesis language: English (default), Chinese, French, German, Italian, Japanese, Korean, Portuguese, Russian, Spanish, or Auto (let the model detect)
- **Parallel Workers** - Batch size for fast batch rendering (higher = more VRAM usage)
- **Batch Seed** - Fixed seed for reproducible batch output (leave empty for random)
- **Compile Codec** - Enable `torch.compile` for 3-4x faster batch decoding (adds ~30-60s warmup on first generation)
- **Sub-batching** - Split batches by text length to reduce wasted GPU compute on padding (enabled by default)
- **Min Sub-batch Size** - Minimum chunks per sub-batch before allowing a split (default: 4)
- **Length Ratio** - Maximum longest/shortest text length ratio before forcing a sub-batch split (default: 5)
- **Max Chars** - Maximum total characters per sub-batch; lower values reduce VRAM usage (default: 3000)

**Prompt Settings (Advanced):**
- **Generation Settings** - Chunk size and max tokens for LLM responses
- **LLM Sampling Parameters** - Temperature, Top P, Top K, Min P, and Presence Penalty
- **Banned Tokens** - Comma-separated list of tokens to ban from LLM output (useful for disabling thinking mode on models like GLM4, DeepSeek-R1, etc.)
- **Prompt Customization** - System and user prompts used for script generation. Defaults are loaded from `default_prompts.txt` and can be customized per-session in the UI. Click "Reset to Defaults" to reload the file-based defaults (picks up edits without restarting the app)
- **Voice Suggestion Prompt** - Controls how the LLM converts source excerpts for a named character into a single JSON `voice` description. The default is loaded from `voice_prompt.txt`

### Script Tab
Upload a text file and generate the annotated script. The LLM converts your book into a structured JSON format with:
- Speaker identification (NARRATOR vs character names)
- Dialogue text with natural vocalizations (written as pronounceable text, not tags)
- Style directions for TTS delivery

**Review Script** - After generation, click "Review Script" to run a second LLM pass that detects and fixes common annotation errors:
1. Attribution tags left in dialogue ("said he", "she replied") are stripped
2. Narration mixed into character entries is split out as NARRATOR
3. Dialogue embedded in narrator entries is extracted as the correct speaker
4. Short consecutive narrator entries covering the same scene are merged
5. Invalid instruct fields (physical actions instead of voice directions) are corrected

Review prompts are customizable in `review_prompts.txt` (same format as `default_prompts.txt`).

### Voices Tab
After script generation, voices are automatically loaded from the annotated script. For each speaker:

**Custom Voice Mode:**
- Select from 9 pre-trained voices: Aiden, Dylan, Eric, Ono_anna, Ryan, Serena, Sohee, Uncle_fu, Vivian
- Set a character style that appends persistent traits to every TTS instruct (e.g., "Heavy Scottish accent", "Refined aristocratic tone")
- Optionally set a seed for reproducible output

**Clone Voice Mode:**
- Select a designed voice or enter a custom reference audio path
- Provide the exact transcript of the reference
- Note: Instruct directions are ignored for cloned voices

**LoRA Voice Mode:**
- Select a trained LoRA adapter from the Training tab
- Set a character style (same as Custom — appended to every instruct)
- Combines voice identity from training with instruct-following from the Base model

**Voice Design Mode:**
- Set a base voice description (e.g., "Young strong soldier")
- Each line's instruct is appended as delivery/emotion direction
- Generates voice on-the-fly using the VoiceDesign model — ideal for minor characters

### Voice Designer Tab
Create new voices from text descriptions without needing reference audio.

- **Describe a voice** in natural language (e.g., "A warm elderly woman with a gentle, raspy voice and a slight Southern drawl")
- **Preview** the voice with sample text before saving
- **Save to library** for use as clone voice references in the Voices tab
- Uses the Qwen3-TTS VoiceDesign model to synthesize voice characteristics from descriptions

### Training Tab
Train LoRA adapters on the Base model to create custom voice identities. Several built-in LoRA presets are included out of the box and appear alongside your trained adapters.

**Dataset:**
- **Upload ZIP** — WAV files (24kHz mono) + `metadata.jsonl` with `audio_filepath` and `text` fields
- **Generate Dataset** — Auto-generate training samples from a Voice Designer description with custom sample texts
- **Dataset Builder** — Interactive tool in its own tab (see below) for building datasets sample-by-sample with preview

**Training Configuration:**
- **Adapter Name** — Identifier for the trained model
- **Epochs** — Full passes over the dataset (15-30 recommended for 20+ samples)
- **Learning Rate** — Default 5e-6 (conservative). Higher trains faster but risks instability
- **LoRA Rank** — Adapter capacity. High (64+) locks voice identity strongly but can flatten delivery. Low (8-16) preserves expressiveness
- **LoRA Alpha** — Scaling factor. Effective strength = alpha / rank. Common starting point: alpha = 2x rank
- **Batch Size / Grad Accum** — Batch 1 with gradient accumulation 8 is typical for 24GB cards

**Training tips:**
- Include samples with varied emotions (happy, sad, angry, calm) for expressive voices
- Neutral-only training data produces flat voices that resist instruct prompting
- The settings info panel in the UI explains each parameter's effect on voice quality

### Dataset Builder Tab
Build LoRA training datasets interactively, one sample at a time.

- **Create a project** with a voice description and optional global seed
- **Define samples** — Set text and emotion/style per row
- **Preview audio** — Generate and listen to individual samples or batch-generate all at once
- **Cancel batch** — Stop a running batch generation without losing completed samples
- **Save as dataset** — Export the project as a training-ready dataset that appears in the Training tab
- Designed voices and Voice Designer descriptions drive the audio generation via Qwen3-TTS VoiceDesign model

### Editor Tab
Fine-tune your audiobook before export:
- **View all chunks** in a table with status indicators
- **Edit inline** - Click to modify speaker, text, or instruct
- **Generate single** - Regenerate just one chunk after editing
- **Batch render** - Process all pending chunks (see Render Modes below)
- **Play sequence** - Preview audio playback in order
- **Merge all** - Combine chunks into final audiobook

### Render Modes

Alexandria offers two methods for batch rendering audio:

#### Render Pending (Standard)
The default rendering mode. Sends individual TTS calls in parallel using the configured worker count.

- **Per-speaker seeds** - Each voice uses its configured seed for reproducible output
- **Voice cloning support** - Works with both custom voices and cloned voices

#### Batch (Fast)
High-speed rendering that sends multiple lines to the TTS engine in a single batched call. Chunks are sorted by text length and processed in optimized sub-batches to minimize padding waste.

- **3-6x real-time throughput** - With codec compilation enabled, batches of 20-60 chunks process at 3-6x real-time speed
- **Sub-batching** - Automatically groups similarly-sized chunks together for efficient GPU utilization
- **Single seed** - All voices share the `Batch Seed` from config (set empty for random)
- **All voice types supported** - Custom, Clone, and LoRA voices are batched; Voice Design is sequential
- **Parallel Workers** setting controls batch size (higher values use more VRAM)

### Result Tab
Download your completed audiobook as MP3, export as **M4B** with chapter markers for audiobook players, or click **Export to Audacity** for per-speaker WAV tracks.

- **Download MP3** - Standard merged audiobook
- **Export M4B** - AAC audiobook with chapter markers. By default, chapters are auto-detected from headings in the script (e.g. "Chapter 1", "Prologue"). Toggle **Per-chunk chapters** for fine-grained navigation where every line becomes a chapter.
- **Export to Audacity** - Zip with per-speaker WAV tracks. Unzip and open `project.lof` in Audacity to load all tracks, then import `labels.txt` via File > Import > Labels for chunk annotations.

> **Note:** Some Linux audiobook players (e.g. Cozy) have limited M4B support and may not detect the file. The M4B output has been tested with VLC, Haruna, and Audiobookshelf.

## Performance

### Recommended Settings for Batch Generation

| Setting | Recommended | Notes |
|---------|-------------|-------|
| TTS Mode | `local` | Built-in engine, no external server |
| Compile Codec | `true` | 3-4x faster decoding after one-time warmup |
| Parallel Workers | 20-60 | Higher = more throughput, more VRAM |
| Render Mode | Batch (Fast) | Uses batched TTS calls |

### Benchmarks

Tested on AMD RX 7900 XTX (24 GB VRAM, ROCm 6.3):

| Configuration | Throughput |
|--------------|------------|
| Standard mode (sequential) | ~1x real-time |
| Batch mode, no codec compile | ~2x real-time |
| Batch mode + compile_codec | **3-6x real-time** |

A 273-chunk audiobook (~54 minutes of audio) generates in approximately 16 minutes with batch mode and codec compilation enabled.

### ROCm (AMD GPU) Notes

> **Linux only.** AMD GPU acceleration requires ROCm 6.3 on Linux. AMD GPUs on Windows run in CPU mode — see [GPU Compatibility](#gpu-compatibility).

Alexandria automatically applies ROCm-specific optimizations when running on AMD GPUs:
- **MIOpen fast-find mode** - Prevents workspace allocation failures that cause slow GEMM fallback
- **Triton AMD flash attention** - Enables native flash attention for the whisper encoder
- **triton_key compatibility shim** - Fixes `torch.compile` on pytorch-triton-rocm

These are applied transparently and require no configuration.

## Script Format

The generated script is a JSON array with `speaker`, `text`, and `instruct` fields:

```json
[
  {"speaker": "NARRATOR", "text": "The door creaked open slowly.", "instruct": "Calm, even narration."},
  {"speaker": "ELENA", "text": "Ah! Who's there?", "instruct": "Startled and fearful, sharp whispered question, voice cracking with panic."},
  {"speaker": "MARCUS", "text": "Haha... did you miss me?", "instruct": "Menacing confidence, low smug drawl with a dark chuckle, savoring the moment."}
]
```

- **`instruct`** — 2-3 sentence TTS voice direction sent directly to the engine. Set tone, describe delivery, then give specific references. Example: "Devastated by grief, Sniffing between words and pausing to collect herself, end with a wracking sob."

### Non-verbal Sounds
Vocalizations are written as real pronounceable text that the TTS speaks directly — no bracket tags or special tokens. The LLM generates natural onomatopoeia with short instruct directions:
- Gasps: "Ah!", "Oh!" with instruct like "Fearful, sharp gasp."
- Sighs: "Haah...", "Hff..."
- Laughter: "Haha!", "Ahaha..."
- Crying: "Hic... sniff..."
- Exclamations: "Mmm...", "Hmm...", "Ugh..."

## Output Files

**Final Audiobook:**
- `cloned_audiobook.mp3` - Combined audiobook with natural pauses

**Individual Voicelines (for DAW editing):**
```
voicelines/
├── voiceline_0001_narrator.mp3
├── voiceline_0002_elena.mp3
├── voiceline_0003_marcus.mp3
└── ...
```

Files are numbered in timeline order with speaker names for easy:
- Import into Audacity or other DAWs
- Placement on separate character tracks
- Fine-tuning of timing and effects

**Audacity Export (per-speaker tracks):**
```
audacity_export.zip
├── project.lof       # Open this in Audacity to import all tracks
├── labels.txt        # Import via File > Import > Labels for chunk annotations
├── narrator.wav      # Full-length track with only NARRATOR audio
├── elena.wav         # Full-length track with only ELENA audio
├── marcus.wav        # Full-length track with only MARCUS audio
└── ...
```

Each WAV track is padded to the same total duration with silence where other speakers are talking. Playing all tracks simultaneously sounds identical to the merged MP3.

**M4B Audiobook (chaptered):**
- `audiobook.m4b` - AAC audiobook with embedded chapter markers
- Chapters auto-detected from script headings, or per-chunk when toggled
- Compatible with Audiobookshelf, Apple Books, VLC, Haruna, and most audiobook players

## Technical Docs

Deep technical docs moved to wiki-style pages in `wiki/`:

- [Wiki Home](wiki/Home.md)
- [API Reference](wiki/API-Reference.md)
- [Automation Examples (Python/JavaScript)](wiki/Automation-Examples.md)
- [Project Structure](wiki/Project-Structure.md)
- [Troubleshooting](wiki/Troubleshooting.md)

## Recommended LLM Models

For script generation, non-thinking models work best:
- **Qwen3-next** (80B-A3B-instruct) - Excellent JSON output and instruct directions
- **Gemma3** (27B recommended) - Strong JSON output and instruct directions
- **Qwen2.5** (any size) - Reliable JSON output
- **Qwen3** (non-thinking variant)
- **Llama 3.1/3.2** - Good character distinction
- **Mistral/Mixtral** - Fast and reliable

**Thinking models** (DeepSeek-R1, GLM4-air, etc.) can interfere with JSON output. If you must use one, add `<think>` to the **Banned Tokens** field in Setup to disable thinking mode.

## Prompt Customization

LLM prompts are stored in plain-text files at the project root, split into system prompt and user prompt sections by a `---SEPARATOR---` delimiter:

- **`default_prompts.txt`** — Prompts for script generation (annotation)
- **`review_prompts.txt`** — Prompts for script review (error correction)

**How it works:**
- `app/default_prompts.py` and `app/review_prompts.py` read their respective files and export the prompts
- Prompts hot-reload from disk on every request, so edits take effect immediately without restarting the app
- `config.json` stores user overrides for generation prompts — when its prompt fields are empty, the file defaults are used
- The "Reset to Defaults" button in the Web UI fetches the latest file defaults via `/api/default_prompts`

**To customize prompts:**
1. **Temporary (per-session):** Edit generation prompts directly in the Setup tab's Prompt Customization section
2. **Permanent (all sessions):** Edit `default_prompts.txt` or `review_prompts.txt` directly — changes are picked up on the next request

**Non-English books:** The default LLM prompts are written for English text and reference English-specific conventions (attribution tags like "said he", quotation marks, etc.). When processing books in other languages, you'll get better results by editing the prompts to match that language's dialogue conventions — for example, French guillemets (« »), Japanese brackets (「」), or language-appropriate attribution patterns. Set the TTS **Language** dropdown to match as well.

## Project Structure

See the wiki page: [Project Structure](wiki/Project-Structure.md).

## License

MIT

### Third-Party Licenses
- [qwen_tts](https://github.com/Qwen/Qwen3-TTS) — Apache License 2.0, Copyright Alibaba Qwen Team
