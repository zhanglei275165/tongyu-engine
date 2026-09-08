# -*- coding: utf-8 -*-
"""
同宇引擎 (Tongyu Engine)
=======================
仿 Ollama 的本地模型服务，纯 Python + llama-cpp-python，零外部依赖、零 Key。
- 监听 127.0.0.1:11434，提供与 Ollama 完全兼容的 /api/tags、/api/generate 接口
  （写书流水线脚本无需任何改动即可接入）。
- 直接读取本机已缓存的 GGUF 模型权重（~/.ollama/models），不联网、不下载。
- 限线程运行（默认 4），避免占满 CPU 卡顿。
- 带 Windows 系统托盘图标（默认）：可“打开同宇AI / 查看状态 / 退出引擎”。
- 加 --no-tray 则以纯后台服务模式运行（供流水线夜间编排器拉起）。
"""
import os
import sys
import json
import time
import datetime
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import llama_cpp
import pystray
from PIL import Image, ImageDraw
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 11434
N_THREADS = int(os.environ.get("TY_THREADS", "4"))
MAX_CTX = 4096
GGUF_DIRS = [
    os.path.expanduser("~/.ollama/models"),
    "C:/Users/Administrator/.ollama/models",
]

MODEL_CACHE = {}      # 模型名 -> GGUF 绝对路径
LLM_CACHE = {}         # GGUF 路径 -> 已加载的 Llama 实例
HUB = {"status": "启动中", "last_model": "", "reqs": 0, "running": True}
_server = None


def log(msg):
    HUB["status"] = msg
    try:
        with open(os.path.join(HERE, "engine.log"), "a", encoding="utf-8") as f:
            f.write(datetime.datetime.now().strftime("%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def discover():
    """扫描本机 .ollama 缓存，找出可直接使用的 GGUF 模型权重。"""
    found = {}
    seen = set()
    for base in GGUF_DIRS:
        man = os.path.join(base, "manifests", "registry.ollama.ai", "library")
        blobs = os.path.join(base, "blobs")
        if not os.path.isdir(man):
            continue
        for name in sorted(os.listdir(man)):
            ndir = os.path.join(man, name)
            if not os.path.isdir(ndir):
                continue
            for tag in sorted(os.listdir(ndir)):
                try:
                    with open(os.path.join(ndir, tag), encoding="utf-8") as fh:
                        m = json.load(fh)
                except Exception:
                    continue
                blob = None
                for layer in m.get("layers", []):
                    if layer.get("mediaType") == "application/vnd.ollama.image.model":
                        blob = layer.get("digest")
                        break
                if not blob:
                    continue
                bf = os.path.normpath(os.path.join(blobs, blob.replace("sha256:", "sha256-")))
                if not os.path.isfile(bf):
                    continue
                if bf in seen:
                    continue
                # 跳过嵌入/视觉等非聊天模型
                nl = (name + ":" + tag).lower()
                if "embed" in nl or "minicpm" in nl or "clip" in nl:
                    continue
                seen.add(bf)
                found[f"{name}:{tag}"] = bf
    # 让 qwen2.5-coder:3b 排在最前（写书流水线默认模型，优先加载）
    pref = [k for k in found if "qwen2.5-coder:3b" in k]
    rest = [k for k in found if k not in pref]
    ordered = pref + sorted(rest)
    return {k: found[k] for k in ordered}


def resolve(name):
    if name in MODEL_CACHE:
        return MODEL_CACHE[name]
    # 模糊匹配：名含请求串，或请求串含模型基名
    for k, v in MODEL_CACHE.items():
        if name and (name in k or k.split(":")[0] in name):
            return v
    return None


def get_llm(name):
    path = resolve(name)
    if not path:
        return None
    if path not in LLM_CACHE:
        try:
            log("加载模型 %s (线程=%d) ..." % (os.path.basename(path), N_THREADS))
            LLM_CACHE[path] = llama_cpp.Llama(
                model_path=path, n_threads=N_THREADS, n_ctx=MAX_CTX,
                n_batch=512, verbose=False)
            log("模型就绪: %s" % os.path.basename(path))
        except Exception as e:
            log("模型加载失败: %s | %s" % (os.path.basename(path), e))
            return None
    return LLM_CACHE[path]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.rstrip("/")
        if p in ("/api/tags", ""):
            models = [{
                "name": k, "model": k,
                "size": os.path.getsize(v),
                "modified_at": datetime.datetime.now().isoformat(),
            } for k, v in MODEL_CACHE.items()]
            self._send(200, {"models": models})
        elif p in ("/", "/api/version"):
            self._send(200, {"version": "tongyu-engine/1.0"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") not in ("/api/generate",):
            self._send(404, {"error": "not found"})
            return
        try:
            ln = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            self._send(400, {"error": "bad json"})
            return
        model = body.get("model", "")
        prompt = body.get("prompt", "")
        opts = body.get("options", {}) or {}
        temp = float(opts.get("temperature", 0.7))
        top_p = float(opts.get("top_p", 0.9))
        top_k = int(opts.get("top_k", 40))
        n_pred = int(opts.get("num_predict", 256))
        stop = opts.get("stop", []) or []
        rep_pen = float(opts.get("repeat_penalty", 1.1))

        llm = get_llm(model)
        if llm is None:
            self._send(500, {"error": "no model available", "done": True})
            return
        HUB["reqs"] += 1
        HUB["last_model"] = model
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            gen = llm.create_completion(
                prompt, stream=True, max_tokens=n_pred,
                temperature=temp, top_p=top_p, top_k=top_k,
                repeat_penalty=rep_pen, stop=stop)
            for chunk in gen:
                text = chunk["choices"][0]["text"]
                self.wfile.write((json.dumps(
                    {"model": model, "response": text, "done": False},
                    ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            self.wfile.write((json.dumps(
                {"model": model, "done": True}, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception as e:
            try:
                self.wfile.write((json.dumps(
                    {"error": str(e), "done": True}, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:
                pass


def make_icon():
    img = Image.new("RGBA", (64, 64), (196, 30, 30, 255))
    d = ImageDraw.Draw(img)
    try:
        d.text((20, 14), "同", fill=(255, 255, 255, 255))
    except Exception:
        pass
    return img


def open_web(icon, item):
    webbrowser.open("http://127.0.0.1:8585")


def show_status(icon, item):
    icon.notify(
        "同宇引擎运行中\n模型: %s\n请求数: %d\n线程: %d" % (
            HUB["last_model"] or "未加载", HUB["reqs"], N_THREADS),
        "同宇AI 引擎")


def quit_app(icon, item):
    HUB["running"] = False
    try:
        _server.shutdown()
    except Exception:
        pass
    icon.stop()


def main():
    global _server
    MODEL_CACHE.update(discover())
    log("发现模型 %d 个" % len(MODEL_CACHE))
    _server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    log("同宇引擎已启动 端口 %d 线程 %d" % (PORT, N_THREADS))

    if "--no-tray" in sys.argv:
        # 纯后台服务模式（供夜间编排器拉起），无 GUI
        try:
            while HUB["running"]:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        _server.shutdown()
        return

    icon = pystray.Icon("tongyu_engine", make_icon(), "同宇AI 引擎")
    icon.menu = pystray.Menu(
        pystray.MenuItem("打开同宇AI", open_web),
        pystray.MenuItem("查看状态", show_status),
        pystray.MenuItem("退出引擎", quit_app),
    )
    try:
        icon.run()
    except Exception as e:
        # 无桌面/托盘不可用的环境：降级为纯后台服务
        log("托盘不可用，降级后台模式: %s" % e)
        try:
            while HUB["running"]:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        _server.shutdown()


if __name__ == "__main__":
    main()
