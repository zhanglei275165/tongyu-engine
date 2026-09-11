# -*- coding: utf-8 -*-
"""
同宇引擎 (Tongyu Engine)
=======================
仿 Ollama 的本地模型服务，纯 Python + llama-cpp-python，零外部依赖、零 Key。
- 监听本机端口（默认 127.0.0.1:11434），提供与 Ollama 兼容的接口：
    /api/version、/api/tags、/api/generate、/api/chat、/api/show
  （写书流水线脚本无需任何改动即可接入 /api/generate、/api/chat）。
- 直接读取本机已缓存的 GGUF 模型权重（~/.ollama/models），不联网、不下载。
- 限线程运行（默认 4），避免占满 CPU 卡顿。
- 推理串行化（threading.Lock）：杜绝并发共用同一 Llama 实例导致的段错误/崩溃。
- 带 Windows 系统托盘图标（默认）：可“查看状态 / 退出引擎”。
- 加 --no-tray 则以纯后台服务模式运行（供流水线夜间编排器拉起），支持
  SIGINT/SIGTERM 优雅关闭，适合配进程守护长期运行。
"""
import os
import sys
import json
import time
import argparse
import datetime
import threading
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import llama_cpp
import pystray
from PIL import Image, ImageDraw
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 可配置项（可被命令行参数覆盖） ----
HOST = "127.0.0.1"
PORT = 11434
N_THREADS = int(os.environ.get("TY_THREADS", "4"))
MAX_CTX = 4096
GGUF_DIRS = [
    os.path.expanduser("~/.ollama/models"),
    "C:/Users/Administrator/.ollama/models",
]

MODEL_CACHE = {}      # 模型名 -> GGUF 绝对路径
LLM_CACHE = {}         # GGUF 路径 -> 已加载的 Llama 实例
LLM_LOCK = threading.Lock()   # 推理串行锁，避免并发共用实例崩溃
HUB = {"status": "启动中", "last_model": "", "reqs": 0, "running": True}
_server = None
_icon = None


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
        # 双重检查 + 加锁，避免多线程并发重复加载
        with LLM_LOCK:
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


def _opts_from(body):
    """从请求体解析推理超参（generate/chat 通用）。"""
    opts = body.get("options", {}) or {}
    return {
        "temperature": float(opts.get("temperature", 0.7)),
        "top_p": float(opts.get("top_p", 0.9)),
        "top_k": int(opts.get("top_k", 40)),
        "max_tokens": int(opts.get("num_predict", 256)),
        "repeat_penalty": float(opts.get("repeat_penalty", 1.1)),
        "stop": opts.get("stop", []) or [],
    }


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
            self._send(200, {"version": "tongyu-engine/1.1"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.rstrip("/")
        if p not in ("/api/generate", "/api/chat", "/api/show"):
            self._send(404, {"error": "not found"})
            return
        try:
            ln = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            self._send(400, {"error": "bad json"})
            return

        if p == "/api/show":
            self._handle_show(body)
            return

        model = body.get("model", "")
        llm = get_llm(model)
        if llm is None:
            self._send(500, {"error": "no model available", "done": True})
            return
        HUB["reqs"] += 1
        HUB["last_model"] = model

        try:
            if p == "/api/generate":
                self._stream_generate(model, llm, body)
            else:
                self._stream_chat(model, llm, body)
        except Exception as e:
            try:
                self.wfile.write((json.dumps(
                    {"error": str(e), "done": True}, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:
                pass

    # ---- 各端点实现 ----
    def _stream_generate(self, model, llm, body):
        prompt = body.get("prompt", "")
        o = _opts_from(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        with LLM_LOCK:
            gen = llm.create_completion(
                prompt, stream=True, max_tokens=o["max_tokens"],
                temperature=o["temperature"], top_p=o["top_p"], top_k=o["top_k"],
                repeat_penalty=o["repeat_penalty"], stop=o["stop"])
            for chunk in gen:
                text = chunk["choices"][0]["text"]
                self.wfile.write((json.dumps(
                    {"model": model, "response": text, "done": False},
                    ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            self.wfile.write((json.dumps(
                {"model": model, "done": True}, ensure_ascii=False) + "\n").encode("utf-8"))

    def _stream_chat(self, model, llm, body):
        messages = body.get("messages", []) or []
        o = _opts_from(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        with LLM_LOCK:
            gen = llm.create_chat_completion(
                messages=messages, stream=True, max_tokens=o["max_tokens"],
                temperature=o["temperature"], top_p=o["top_p"], top_k=o["top_k"],
                repeat_penalty=o["repeat_penalty"], stop=o["stop"])
            for chunk in gen:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                self.wfile.write((json.dumps(
                    {"model": model,
                     "message": {"role": "assistant", "content": content},
                     "done": False},
                    ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            self.wfile.write((json.dumps(
                {"model": model,
                 "message": {"role": "assistant", "content": ""},
                 "done": True, "done_reason": "stop"},
                ensure_ascii=False) + "\n").encode("utf-8"))

    def _handle_show(self, body):
        model = body.get("model", "")
        path = resolve(model)
        if not path:
            self._send(404, {"error": "model not found"})
            return
        info = {
            "model": model,
            "details": {
                "format": "gguf",
                "family": "unknown",
                "parameter_size": "unknown",
                "quantization_level": "unknown",
            },
            "model_info": {},
            "template": "",
            "system": "",
            "parameters": {"num_ctx": MAX_CTX, "num_thread": N_THREADS},
            "path": path,
            "size": os.path.getsize(path),
        }
        # 尽量从 GGUF 元数据提取真实信息
        try:
            llm = get_llm(model)
            md = getattr(llm, "metadata", None) or {}
            info["model_info"] = {k: str(v) for k, v in md.items()}
            fam = str(md.get("general.architecture", "")).lower()
            if fam:
                info["details"]["family"] = fam
            ps = md.get("general.size_label") or md.get("general.parameter_count")
            if ps:
                info["details"]["parameter_size"] = str(ps)
            ql = md.get("quantization.quantization_level") or md.get("general.file_type")
            if ql is not None:
                info["details"]["quantization_level"] = str(ql)
        except Exception:
            pass
        self._send(200, info)


def make_icon():
    img = Image.new("RGBA", (64, 64), (196, 30, 30, 255))
    d = ImageDraw.Draw(img)
    try:
        d.text((20, 14), "同", fill=(255, 255, 255, 255))
    except Exception:
        pass
    return img


def open_web(icon, item):
    # 本引擎为本地推理服务，无对外网页；改为弹出状态通知
    show_status(icon, item)


def show_status(icon, item):
    icon.notify(
        "同宇引擎运行中\n模型: %s\n请求数: %d\n线程: %d\n端口: %s:%d" % (
            HUB["last_model"] or "未加载", HUB["reqs"], N_THREADS, HOST, PORT),
        "同宇AI 引擎")


def quit_app(icon, item):
    shutdown()


def shutdown(signum=None, frame=None):
    HUB["running"] = False
    log("收到关闭信号，正在优雅退出 ...")
    try:
        if _server is not None:
            _server.shutdown()
    except Exception:
        pass
    try:
        if _icon is not None:
            _icon.stop()
    except Exception:
        pass


def serve_forever_no_tray():
    global _server
    _server = ThreadingHTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    log("同宇引擎已启动 %s:%d 线程 %d" % (HOST, PORT, N_THREADS))
    try:
        while HUB["running"]:
            time.sleep(1)
    except (KeyboardInterrupt, InterruptedError):
        pass
    finally:
        _server.shutdown()


def main():
    global HOST, PORT, N_THREADS, GGUF_DIRS, _server
    ap = argparse.ArgumentParser(description="同宇引擎 - 仿 Ollama 本地模型服务")
    ap.add_argument("--host", default=HOST, help="监听地址 (默认 127.0.0.1)")
    ap.add_argument("--port", type=int, default=PORT, help="监听端口 (默认 11434)")
    ap.add_argument("--threads", type=int, default=N_THREADS, help="推理线程数 (默认 4)")
    ap.add_argument("--model-dir", action="append", default=[],
                    help="额外 GGUF 模型目录（可重复指定）")
    ap.add_argument("--no-tray", action="store_true",
                    help="纯后台服务模式（无系统托盘，供编排器拉起）")
    args = ap.parse_args()

    HOST = args.host
    PORT = args.port
    N_THREADS = args.threads
    if args.model_dir:
        GGUF_DIRS = args.model_dir + GGUF_DIRS

    # 优雅关闭信号
    try:
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
    except Exception:
        pass

    MODEL_CACHE.update(discover())
    log("发现模型 %d 个" % len(MODEL_CACHE))

    if args.no_tray:
        serve_forever_no_tray()
        return

    _server = ThreadingHTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    log("同宇引擎已启动 %s:%d 线程 %d" % (HOST, PORT, N_THREADS))

    icon = pystray.Icon("tongyu_engine", make_icon(), "同宇AI 引擎")
    icon.menu = pystray.Menu(
        pystray.MenuItem("查看状态", show_status),
        pystray.MenuItem("退出引擎", quit_app),
    )
    try:
        icon.run()
    except Exception as e:
        # 无桌面/托盘不可用的环境：降级为纯后台服务
        log("托盘不可用，降级后台模式: %s" % e)
        serve_forever_no_tray()


if __name__ == "__main__":
    main()
