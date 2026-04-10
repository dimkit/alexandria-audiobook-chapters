# Model Recommendations

Threadspeak uses LLMs in multiple stages (for example dialogue attribution, temperament extraction, and voice suggestion tasks).

## General guidance

- Tool use required.
- If a model emits unwanted control text, use banned-token controls in Setup.

## Common choices

- Qwen 3.5 
- Gemma 4 
- Llama instruct variants
- GPT-OSS

Longer context allows the model to extract speaker more accurately but increases runtime. Current implementation relies on explicit model tool use to provide output, so will fail on models without this capability.
Model quality and behavior can vary by provider/runtime. Validate on a representative sample chapter before long runs.
