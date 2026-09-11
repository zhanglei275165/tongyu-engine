# -*- coding: utf-8 -*-
"""同宇引擎冒烟测试：进程内启动 Server，用 urllib（禁用代理）探测各接口。"""
import os, sys, time, threading, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 同宇引擎 as e

e.HOST = "127.0.0.1"
e.PORT = 18080
e.N_THREADS = 2
# 使用默认 GGUF_DIRS（含 ~/.ollama/models 与 C:/Users/Administrator/.ollama/models）
e.MODEL_CACHE.update(e.discover())

# 禁用代理，直连 127.0.0.1
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

srv = e.ThreadingHTTPServer((e.HOST, e.PORT), e.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print("[test] 引擎已启动 %s:%d，模型 %d 个" % (e.HOST, e.PORT, len(e.MODEL_CACHE)))
time.sleep(1)

MODEL = "qwen2.5-coder:3b"
base = "http://%s:%d" % (e.HOST, e.PORT)
results = {}

def call(method, path, payload=None, timeout=120):
    url = base + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    return r.status, body

# 1) version
try:
    st, body = call("GET", "/api/version")
    results["/api/version"] = (st == 200 and "tongyu-engine" in body, body.strip())
except Exception as ex:
    results["/api/version"] = (False, "ERR %s" % ex)

# 2) tags
try:
    st, body = call("GET", "/api/tags")
    ok = st == 200 and MODEL in body
    results["/api/tags"] = (ok, body.strip()[:120])
except Exception as ex:
    results["/api/tags"] = (False, "ERR %s" % ex)

# 3) generate
try:
    st, body = call("POST", "/api/generate",
                    {"model": MODEL, "prompt": "用一句话介绍明朝。", "stream": True, "options": {"num_predict": 32}})
    lines = [l for l in body.strip().split("\n") if l]
    ok = st == 200 and any(json.loads(l).get("done") for l in lines) and len(lines) > 1
    results["/api/generate"] = (ok, "lines=%d last=%s" % (len(lines), lines[-1][:80]))
except Exception as ex:
    results["/api/generate"] = (False, "ERR %s" % ex)

# 4) chat
try:
    st, body = call("POST", "/api/chat",
                    {"model": MODEL, "messages": [{"role": "user", "content": "你好，你是谁？"}],
                     "stream": True, "options": {"num_predict": 32}})
    lines = [l for l in body.strip().split("\n") if l]
    ok = st == 200 and any(json.loads(l).get("done") for l in lines)
    # 验证 message.content 累积非空
    content = "".join(json.loads(l).get("message", {}).get("content", "") for l in lines if not json.loads(l).get("done"))
    results["/api/chat"] = (ok and len(content) > 0, "lines=%d content=%r" % (len(lines), content[:60]))
except Exception as ex:
    results["/api/chat"] = (False, "ERR %s" % ex)

# 5) show
try:
    st, body = call("POST", "/api/show", {"model": MODEL})
    ok = st == 200 and "model" in body
    results["/api/show"] = (ok, body.strip()[:120])
except Exception as ex:
    results["/api/show"] = (False, "ERR %s" % ex)

print("\n==== 冒烟测试结果 ====")
allok = True
for k, (ok, detail) in results.items():
    allok = allok and ok
    print("%-16s %s  %s" % (k, "PASS" if ok else "FAIL", detail))
print("===================")
print("OVERALL:", "ALL PASS" if allok else "HAS FAILURE")
srv.shutdown()
sys.exit(0 if allok else 1)
