# Tongyu Engine

> A local, Ollama-compatible model server. Pure Python + [llama-cpp-python](https://github.com/abetlen/llama-cpp-python). Zero external dependencies, zero API key, runs on CPU.

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-Windows-blue)

## Why this exists

Official Ollama may default to the integrated GPU (Vulkan) on some machines, saturate the CPU, and slow the whole computer. Tongyu Engine is a lightweight alternative you fully control:

- **Ollama-compatible API** for writing/serving scenarios: listens on `127.0.0.1:11434`, serves `/api/version`, `/api/tags`, `/api/generate`, `/api/chat`, and `/api/show`. Your existing writing scripts and AI customer service connect unchanged (defaults to `/api/generate` and `/api/chat`).
- **Pure CPU, thread-limited**: 4 threads by default, so your PC stays responsive while generating or batching.
- **Serialized inference (thread lock)**: concurrent requests sharing one model instance are queued automatically, preventing segfaults/crashes from parallel inference.
- **Uses your local GGUF cache**: reads models already on your disk (usually `~/.ollama/models`). No network, no download, no key.
- **Windows system tray**: double-click for a tray icon with status / quit.
- **`--no-tray` background mode**: for pipeline nightly schedulers, runs headless with SIGINT/SIGTERM graceful shutdown.
- **Guard process for 7×24**: ships `tongyu_engine_guard.py` that auto-restarts on crash — ideal for long batch runs.

This is the first building block of the "low-spec PC can do AI" series — run your own local LLM service on an ordinary office laptop.

## Quick start

```bash
pip install llama-cpp-python pystray pillow
python 同宇引擎.py            # with tray
python 同宇引擎.py --no-tray  # headless service mode (for pipelines)

# common flags
python 同宇引擎.py --host 127.0.0.1 --port 11434 --threads 4 --no-tray
python 同宇引擎.py --model-dir "D:/models"   # extra GGUF dir (repeatable)
```

Package as exe:

```bash
pip install pyinstaller
pyinstaller TongyuEngine.spec   # output: dist/TongyuEngine.exe
```

## API example

```bash
curl http://127.0.0.1:11434/api/version
curl http://127.0.0.1:11434/api/tags

curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","prompt":"hello","stream":false}'

curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","messages":[{"role":"user","content":"hello"}]}'

curl -X POST http://127.0.0.1:11434/api/show \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b"}'
```

All endpoints are compatible with Ollama clients (the `ollama` CLI and OpenAI-compatible SDKs' Ollama backend). Streaming responses are NDJSON: `/api/generate` emits `{"response":"...","done":false}` per line; `/api/chat` emits `{"message":{"role":"assistant","content":"..."},"done":false}` per line.

## Long-running stability (for 7×24 batch runs)

Tongyu Engine reuses one in-process model instance to save memory. Two safeguards prevent long-run instability:

1. **Inference serialization lock**: all `/api/generate` and `/api/chat` requests pass through a `threading.Lock`, eliminating segfaults from concurrent shared-instance inference (the main cause of prior long-run crashes).
2. **Guard process**: `tongyu_engine_guard.py` probes port `11434` every 30s and auto-restarts the engine if it exits or stops responding.

Recommended: launch via the guard rather than running the engine bare:

```bash
python tongyu_engine_guard.py                 # keeps the engine alive
python tongyu_engine_guard.py --port 11434 --interval 30
python tongyu_engine_guard.py --engine "/opt/tongyu/同宇引擎.py" --python "/usr/bin/python3"
```

On Windows, put `python tongyu_engine_guard.py` into Task Scheduler for boot-on-start + auto-heal.

## License

MIT — free to use, modify, and ship in your own commercial / App-Store products.

---

## Knowledge Planet · 零基础AI造应用·同宇圈

Want structured tutorials on building AI apps, AI audiobooks, and local-model setups? Join my Knowledge Planet for full guides, Q&A, and source updates:

https://wx.zsxq.com/group/48882488185118

Brought to you by Tongyu (AI Audiobook · Tongyu Productions). MIT licensed — free to use, modify, commercialize, and publish.
