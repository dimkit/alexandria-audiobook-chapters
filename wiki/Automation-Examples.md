# Automation Examples

Use this page for programmatic control of the pipeline.

Base URL: `http://127.0.0.1:4200`

## Python

```python
import time
import requests

BASE = "http://127.0.0.1:4200"

with open("mybook.txt", "rb") as f:
    requests.post(f"{BASE}/api/upload", files={"file": f}).raise_for_status()

requests.post(f"{BASE}/api/generate_script").raise_for_status()

while True:
    status = requests.get(f"{BASE}/api/status/script").json()
    if not status.get("running"):
        break
    time.sleep(2)

requests.post(
    f"{BASE}/api/save_voice_config",
    json={"NARRATOR": {"type": "custom", "voice": "Ryan", "character_style": "calm"}},
).raise_for_status()

chunks = requests.get(f"{BASE}/api/chunks").json()
indices = [c["id"] for c in chunks]

requests.post(f"{BASE}/api/generate_batch_fast", json={"indices": indices}).raise_for_status()

while True:
    status = requests.get(f"{BASE}/api/status/audio").json()
    if not status.get("running"):
        break
    time.sleep(2)

requests.post(f"{BASE}/api/merge").raise_for_status()

with open("audiobook.mp3", "wb") as f:
    f.write(requests.get(f"{BASE}/api/audiobook").content)
```

## JavaScript

```javascript
const BASE = "http://127.0.0.1:4200";

const formData = new FormData();
formData.append("file", fileInput.files[0]);
await fetch(`${BASE}/api/upload`, { method: "POST", body: formData });

await fetch(`${BASE}/api/generate_script`, { method: "POST" });

while (true) {
  const status = await (await fetch(`${BASE}/api/status/script`)).json();
  if (!status.running) break;
  await new Promise((r) => setTimeout(r, 2000));
}

await fetch(`${BASE}/api/save_voice_config`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    NARRATOR: { type: "custom", voice: "Ryan", character_style: "calm" }
  })
});

const chunks = await (await fetch(`${BASE}/api/chunks`)).json();
const indices = chunks.map((c) => c.id);

await fetch(`${BASE}/api/generate_batch_fast`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ indices })
});

await fetch(`${BASE}/api/merge`, { method: "POST" });
```
