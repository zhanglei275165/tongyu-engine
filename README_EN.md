# Tongyu Engine

> A local, Ollama-compatible model server. Pure Python + [llama-cpp-python](https://github.com/abetlen/llama-cpp-python). Zero external dependencies, zero API key, runs on CPU.

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-Windows-blue)

## Why this exists

Official Ollama may default to the integrated GPU (Vulkan) on some machines, saturate the CPU, and slow the whole computer. Tongyu Engine is a lightweight alternative you fully control:

- **Ollama-compatible API** for writing/serving scenarios: listens on `127.0.0.1:11434`, serves `/api/tags` and `/api/generate`. Your existing writing scripts and AI customer service connect unchanged (defaults to `/api/generate`).
- **Pure CPU, thread-limited**: 4 threads by default, so your PC stays responsive while generating or batching.
- **Uses your local GGUF cache**: reads models already on your disk (usually `~/.ollama/models`). No network, no download, no key.
- **Windows system tray**: double-click for a tray icon with open / status / quit.
- **`--no-tray` background mode**: for pipeline nightly schedulers, runs headless.

This is the first building block of the "low-spec PC can do AI" series — run your own local LLM service on an ordinary office laptop.

## Quick start

```bash
pip install llama-cpp-python pystray pillow
python 同宇引擎.py            # with tray
python 同宇引擎.py --no-tray  # headless service mode (for pipelines)
```

Package as exe:

```bash
pip install pyinstaller
pyinstaller TongyuEngine.spec   # output: dist/TongyuEngine.exe
```

## API example

```bash
curl http://127.0.0.1:11434/api/tags

curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","prompt":"hello","stream":false}'
```

## License

MIT — free to use, modify, and ship in your own commercial / App-Store products.

---

## Knowledge Planet · 零基础AI造应用·同宇圈

Want structured tutorials on building AI apps, AI audiobooks, and local-model setups? Join my Knowledge Planet for full guides, Q&A, and source updates:

https://wx.zsxq.com/group/48882488185118

Brought to you by Tongyu (AI Audiobook · Tongyu Productions). MIT licensed — free to use, modify, commercialize, and publish.
