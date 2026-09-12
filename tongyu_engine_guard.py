# -*- coding: utf-8 -*-
"""
同宇引擎守护进程 (Tongyu Engine Guard)
=====================================
解决长时间运行不稳定的问题：定时探测引擎端口存活，一旦崩溃/无响应
即自动重启。适合配合 Windows 计划任务 / nohup 长期驻留。

用法:
    python tongyu_engine_guard.py
    python tongyu_engine_guard.py --port 11434 --interval 30
    python tongyu_engine_guard.py --engine "D:/path/同宇引擎.py" --python "python"

退出: 控制台 Ctrl+C，或直接结束本进程（会先杀掉被守护的引擎子进程）。
"""
import os
import sys
import time
import signal
import argparse
import subprocess
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    ts = time.strftime("%m-%d %H:%M:%S")
    line = "[guard %s] %s" % (ts, msg)
    print(line, flush=True)
    try:
        with open(os.path.join(HERE, "guard.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def default_engine():
    # 同目录下的引擎脚本
    p = os.path.join(HERE, "同宇引擎.py")
    return p if os.path.isfile(p) else "同宇引擎.py"


def default_python():
    # 优先使用同目录或环境变量指定的解释器；否则用当前解释器
    return os.environ.get("TY_PYTHON", sys.executable)


def probe(host, port, timeout=5):
    url = "http://%s:%d/api/version" % (host, port)
    try:
        req = urllib.request.Request(url, method="GET")
        # 强制不走系统代理，否则 127.0.0.1 探测会被代理拦截误判引擎挂掉
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, Exception):
        return False


def main():
    ap = argparse.ArgumentParser(description="同宇引擎守护进程")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--interval", type=int, default=30,
                    help="存活探测间隔(秒)，默认 30")
    ap.add_argument("--engine", default=default_engine(),
                    help="引擎脚本路径")
    ap.add_argument("--python", default=default_python(),
                    help="Python 解释器路径")
    ap.add_argument("--extra-args", default="--no-tray",
                    help="传给引擎的额外参数，默认 --no-tray")
    args = ap.parse_args()

    child = None
    running = True

    def stop_child():
        nonlocal child
        if child is not None and child.poll() is None:
            try:
                child.terminate()
                child.wait(timeout=10)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        child = None

    def on_signal(signum, frame):
        nonlocal running
        running = False
        log("收到退出信号，停止守护 ...")
        stop_child()

    try:
        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)
    except Exception:
        pass

    def start_child():
        nonlocal child
        cmd = [args.python, args.engine] + args.extra_args.split()
        log("启动引擎: %s" % " ".join(cmd))
        try:
            child = subprocess.Popen(cmd, cwd=HERE,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        except Exception as e:
            log("引擎启动失败: %s" % e)
            child = None

    log("守护启动，目标 %s:%d，探测间隔 %ds" % (args.host, args.port, args.interval))
    start_child()
    # 给引擎一点启动时间再开始探测
    time.sleep(8)

    while running:
        ok = probe(args.host, args.port)
        if ok:
            time.sleep(args.interval)
            continue
        log("引擎无响应，准备重启 ...")
        stop_child()
        time.sleep(3)
        if not running:
            break
        start_child()
        time.sleep(8)

    stop_child()
    log("守护结束")


if __name__ == "__main__":
    main()
