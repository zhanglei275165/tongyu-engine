# 同宇引擎 (Tongyu Engine)

> 一个**仿 Ollama 的本地模型服务**。纯 Python + [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)，零外部依赖、零 API Key、纯 CPU 也能跑。

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-Windows-blue)

## 为什么要有它

官方 Ollama 在某些机器上会默认走核显（Vulkan）加载、占满 CPU、拖慢整台电脑，而且你想**完全掌控、不依赖第三方软件**时它并不理想。

同宇引擎就是为了解决这个问题而生的：

- ✅ **接口兼容 Ollama 写书/客服场景**：监听 `127.0.0.1:11434`，提供 `/api/version`、`/api/tags`、
  `/api/generate`、`/api/chat`、`/api/show` 五类接口，你原来的写书脚本、AI 客服**一行都不用改**就能接上来
  （默认即 `/api/generate` 与 `/api/chat`）。
- ✅ **纯 CPU、限线程**：默认 4 线程，写代码/跑批时不会卡死电脑。
- ✅ **推理串行化（线程锁）**：多并发请求共用同一模型实例时自动排队，杜绝并发推理导致的段错误/崩溃。
- ✅ **直接吃本地缓存**：读取你电脑上已有的 GGUF 模型权重（通常在 `~/.ollama/models`），不联网、不下载、不填 Key。
- ✅ **带 Windows 系统托盘**：双击就有托盘图标，可「查看状态 / 退出引擎」。
- ✅ **也能 `--no-tray` 后台跑**：供流水线夜间编排器拉起，无 GUI 安静运行，支持 SIGINT/SIGTERM 优雅关闭。
- ✅ **配守护进程长期稳定**：附 `tongyu_engine_guard.py`，崩溃自动重启，适合 7×24 写书/客服跑批。

> 这也是「低配电脑也能做 AI」系列的第一块基石——它让你用一台普通办公本，跑起属于自己的本地大模型服务。

## 快速开始

### 方式一：直接用（需要 Python 环境）

```bash
pip install llama-cpp-python pystray pillow
python 同宇引擎.py            # 带托盘启动
python 同宇引擎.py --no-tray  # 后台服务模式（供流水线调用）

# 常用启动参数
python 同宇引擎.py --host 127.0.0.1 --port 11434 --threads 4 --no-tray
python 同宇引擎.py --model-dir "D:/models"   # 追加额外 GGUF 目录（可重复）
```

### 方式二：打包成 exe（给你这种「不想碰命令行」的人）

```bash
pip install pyinstaller
pyinstaller TongyuEngine.spec   # 产物在 dist/TongyuEngine.exe
```

双击 `TongyuEngine.exe` 即可，托盘常驻；流水线用 `TongyuEngine.exe --no-tray` 拉起。

## 配置

### 环境变量

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `TY_THREADS` | `4` | 推理线程数，调小更省 CPU |
| `TY_PYTHON` | 当前解释器 | 守护脚本拉起引擎用的 Python 路径 |
| 模型目录 | `~/.ollama/models` | 自动扫描里面的 GGUF 权重 |

### 命令行参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `11434` | 监听端口 |
| `--threads` | `4` | 推理线程数 |
| `--model-dir` | 无 | 追加额外 GGUF 目录（可重复指定） |
| `--no-tray` | 否 | 纯后台服务模式（无系统托盘，供编排器拉起，支持信号优雅退出） |

默认会**过滤掉 embedding / 视觉类模型**（如 `nomic-embed`、`minicpm-v`、`clip`），只暴露聊天模型，
避免流水线误调到非文本模型而崩溃。

## 接口示例

```bash
# 查看版本
curl http://127.0.0.1:11434/api/version

# 列出模型
curl http://127.0.0.1:11434/api/tags

# 生成（流式 NDJSON，每行一个 JSON）
curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","prompt":"你好","stream":false}'

# 对话（Ollama /api/chat 兼容，流式返回 message.content）
curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","messages":[{"role":"user","content":"你好"}]}'

# 查看模型信息
curl -X POST http://127.0.0.1:11434/api/show \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b"}'
```

所有接口均兼容 Ollama 客户端（包括 `ollama` CLI 与 `langchain`/`openai` 兼容 SDK 的 Ollama 后端）。
流式响应为 NDJSON：`/api/generate` 每行形如 `{"response":"...","done":false}`，
`/api/chat` 每行形如 `{"message":{"role":"assistant","content":"..."},"done":false}`。

## 目录结构

```
tongyu-engine/
├── 同宇引擎.py            # 引擎本体（llama-cpp-python + pystray + 兼容 API）
├── tongyu_engine_guard.py # 守护进程：崩溃自动重启，适合长期驻留
├── TongyuEngine.spec      # PyInstaller 打包配置（生成 TongyuEngine.exe）
├── requirements.txt
├── README.md
├── README_EN.md
└── LICENSE
```

## 长运行稳定性（7×24 写书/客服必看）

同宇引擎默认在**单进程内复用模型实例**以省内存。长时间高并发推理偶发不稳定，因此内置两道保险：

1. **推理串行锁**：所有 `/api/generate`、`/api/chat` 推理请求经 `threading.Lock` 串行化，杜绝并发共用
   同一 Llama 实例导致的段错误/崩溃（这是此前长时间运行崩溃的主因）。
2. **守护进程**：`tongyu_engine_guard.py` 每 30 秒探测一次 `11434` 端口，发现引擎退出或无响应即自动拉起。

推荐用守护进程拉起引擎（而不是裸跑主程序）：

```bash
# 守护进程会在后台保活引擎；Ctrl+C 退出时会一并清理子进程
python tongyu_engine_guard.py

# 自定义端口 / 探测间隔
python tongyu_engine_guard.py --port 11434 --interval 30

# 指定引擎脚本与 Python 解释器（部署到别的机器时）
python tongyu_engine_guard.py --engine "/opt/tongyu/同宇引擎.py" --python "/usr/bin/python3"
```

> Windows 上可把 `python tongyu_engine_guard.py` 放进「任务计划程序」开机触发，实现开机自启 + 崩溃自愈。

## 许可证

[MIT](LICENSE) —— 可自由使用、修改、商用，也可基于此上架你自己的应用商店产品。

---

## 知识星球 · 零基础AI造应用·同宇圈

想系统学「用 AI 造应用 / 做 AI 有声小说 / 搭本地模型」？加入我的知识星球，看完整教程 + 社群答疑 + 源码更新通知：

https://wx.zsxq.com/group/48882488185118

出品：AI 有声·同宇出品。本项目基于 MIT 许可证开源，可自由使用、修改、商用、上架。
