# Project Structure

High-level layout (selected paths):

```text
alexandria-audiobook.git/
├── app/
│   ├── app.py
│   ├── api/
│   │   ├── main.py
│   │   ├── shared.py
│   │   └── routers/
│   │       ├── config_router.py
│   │       ├── workflow_router.py
│   │       ├── voices_router.py
│   │       ├── editor_audio_router.py
│   │       ├── scripts_router.py
│   │       ├── voice_designer_router.py
│   │       ├── clone_voices_router.py
│   │       ├── lora_router.py
│   │       └── dataset_builder_router.py
│   ├── static/
│   ├── prompt_defaults/
│   └── requirements.txt
├── builtin_lora/
├── scripts/
├── default_prompts.txt
├── review_prompts.txt
├── voice_prompt.txt
├── README.md
└── wiki/
```

Runtime-generated folders and files (for example `clone_voices/`, `designed_voices/`, `lora_datasets/`, `lora_models/`, `voicelines/`, and `app/config.json`) are created/updated while the app runs and are intentionally not treated as static source structure.
