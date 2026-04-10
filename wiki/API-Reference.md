# API Reference

Verified against current FastAPI router declarations under `app/api/`.

Base URL: `http://127.0.0.1:4200`

## Conventions

- Most async/background jobs expose status through `GET /api/status/{task_name}`.
- Common `task_name` values include: `script`, `review`, `sanity`, `repair`, `audio`, `audacity_export`, `m4b_export`, `lora_training`, `dataset_builder`, `processing_workflow`, `new_mode_workflow`.

## Config and setup

- `GET /api/config`
- `POST /api/config`
- `POST /api/config/setup`
- `POST /api/config/export`
- `POST /api/config/preferences`
- `POST /api/config/verify_tool_capability`
- `GET /api/default_prompts`
- `GET /api/factory_default_prompts`
- `POST /api/generation_mode_lock`
- `POST /api/upload`
- `GET /api/narrator_overrides`
- `POST /api/narrator_overrides`
- `GET /api/script_ingestion/preflight`

## Workflow and script pipeline

- `GET /api/nav_task`
- `POST /api/nav_task/set`
- `POST /api/nav_task/release`
- `POST /api/reset_project`
- `POST /api/generate_script`
- `POST /api/review_script`
- `POST /api/script_sanity_check`
- `GET /api/script_sanity_check`
- `POST /api/replace_missing_chunks`
- `GET /api/annotated_script`
- `GET /api/script_info`
- `GET /api/pipeline_step_status`
- `POST /api/processing/start`
- `POST /api/processing/pause`
- `POST /api/new_mode_workflow/start`
- `POST /api/new_mode_workflow/pause`
- `POST /api/reset_new_mode`
- `POST /api/process_paragraphs`
- `POST /api/assign_dialogue`
- `POST /api/extract_temperament`
- `POST /api/create_script`
- `GET /api/status/{task_name}`

## Voices and dictionary

- `GET /api/voices`
- `POST /api/parse_voices`
- `GET /api/voices/settings`
- `POST /api/voices/settings`
- `POST /api/save_voice_config`
- `POST /api/voices/save_config`
- `POST /api/voices/suggest_description`
- `POST /api/voices/design_generate`
- `POST /api/voices/clear_uploaded`
- `GET /api/dictionary`
- `POST /api/dictionary`

## Voice designer and clone voices

- `POST /api/voice_design/preview`
- `POST /api/voice_design/save`
- `GET /api/voice_design/list`
- `DELETE /api/voice_design/{voice_id}`
- `GET /api/clone_voices/list`
- `POST /api/clone_voices/upload`
- `DELETE /api/clone_voices/{voice_id}`

## Chunks, audio, export

- `GET /api/chunks`
- `GET /api/chunks/view`
- `POST /api/chunks/sync_from_script_if_stale`
- `POST /api/chunks/restore`
- `POST /api/chunks/decompose_long_segments`
- `POST /api/chunks/merge_orphans`
- `POST /api/chunks/repair_legacy`
- `POST /api/chunks/reset_to_pending`
- `POST /api/chunks/invalidate_stale_audio`
- `POST /api/chunks/repair_lost_audio`
- `POST /api/chunks/{index}`
- `POST /api/chunks/{index}/insert`
- `POST /api/chunks/{index}/insert_silence`
- `DELETE /api/chunks/{index}`
- `DELETE /api/chapters/{chapter_name}`
- `POST /api/chunks/{index}/generate`
- `POST /api/chunks/{index}/regenerate`
- `POST /api/generate_batch`
- `POST /api/generate_batch_fast`
- `POST /api/cancel_audio`
- `POST /api/trim_cache/clear`
- `POST /api/trim_sanity/first_clip`
- `GET /api/trim_sanity/first_clip`
- `POST /api/assemble_sanity/first5`
- `GET /api/assemble_sanity/first5`
- `POST /api/assemble_sanity/first5_normalized`
- `GET /api/assemble_sanity/first5_normalized`
- `POST /api/merge`
- `POST /api/merge_optimized`
- `GET /api/optimized_export`
- `GET /api/audiobook`
- `POST /api/export_audacity`
- `GET /api/export_audacity`
- `POST /api/merge_m4b`
- `GET /api/audiobook_m4b`
- `POST /api/m4b_cover`
- `DELETE /api/m4b_cover`

## ASR and proofreading

- `GET /api/asr/status`
- `POST /api/asr/transcribe`
- `POST /api/proofread`
- `POST /api/proofread/auto`
- `POST /api/proofread/clear_failures`
- `POST /api/proofread/discard_selection`
- `POST /api/proofread/{index}/validate`
- `POST /api/proofread/{index}/reject`
- `POST /api/proofread/{index}/compare`
- `POST /api/render_prep_state`

## Script and project persistence

- `GET /api/scripts`
- `POST /api/scripts/save`
- `POST /api/scripts/load`
- `DELETE /api/scripts/{name}`
- `GET /api/project_archive`
- `POST /api/project_archive/load`

## LoRA and dataset builder

- `POST /api/lora/upload_dataset`
- `POST /api/lora/generate_dataset`
- `GET /api/lora/datasets`
- `DELETE /api/lora/datasets/{dataset_id}`
- `POST /api/lora/train`
- `GET /api/lora/models`
- `DELETE /api/lora/models/{adapter_id}`
- `POST /api/lora/download/{adapter_id}`
- `POST /api/lora/test`
- `POST /api/lora/preview/{adapter_id}`
- `GET /api/dataset_builder/list`
- `POST /api/dataset_builder/create`
- `POST /api/dataset_builder/update_meta`
- `POST /api/dataset_builder/update_rows`
- `POST /api/dataset_builder/generate_sample`
- `POST /api/dataset_builder/generate_batch`
- `POST /api/dataset_builder/cancel`
- `GET /api/dataset_builder/status/{name}`
- `POST /api/dataset_builder/save`
- `DELETE /api/dataset_builder/{name}`
