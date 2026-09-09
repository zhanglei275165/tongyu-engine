# 同宇引擎 (Tongyu Engine)

> 一个**仿 Ollama 的本地模型服务**。纯 Python + [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)，零外部依赖、零 API Key、纯 CPU 也能跑。

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-Windows-blue)

## 为什么要有它

官方 Ollama 在某些机器上会默认走核显（Vulkan）加载、占满 CPU、拖慢整台电脑，而且你想**完全掌控、不依赖第三方软件**时它并不理想。

同宇引擎就是为了解决这个问题而生的：

- ✅ **接口兼容 Ollama 写书/客服场景**：监听 `127.0.0.1:11434`，提供 `/api/tags`、`/api/generate`，
  你原来的写书脚本、AI 客服**一行都不用改**就能接上来（默认即 `/api/generate`）。
- ✅ **纯 CPU、限线程**：默认 4 线程，写代码/跑批时不会卡死电脑。
- ✅ **直接吃本地缓存**：读取你电脑上已有的 GGUF 模型权重（通常在 `~/.ollama/models`），不联网、不下载、不填 Key。
- ✅ **带 Windows 系统托盘**：双击就有托盘图标，可「打开应用 / 查看状态 / 退出」。
- ✅ **也能 `--no-tray` 后台跑**：供流水线夜间编排器拉起，无 GUI 安静运行。

> 这也是「低配电脑也能做 AI」系列的第一块基石——它让你用一台普通办公本，跑起属于自己的本地大模型服务。

## 快速开始

### 方式一：直接用（需要 Python 环境）

```bash
pip install llama-cpp-python pystray pillow
python 同宇引擎.py            # 带托盘启动
python 同宇引擎.py --no-tray  # 后台服务模式（供流水线调用）
```

### 方式二：打包成 exe（给你这种「不想碰命令行」的人）

```bash
pip install pyinstaller
pyinstaller TongyuEngine.spec   # 产物在 dist/TongyuEngine.exe
```

双击 `TongyuEngine.exe` 即可，托盘常驻；流水线用 `TongyuEngine.exe --no-tray` 拉起。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `TY_THREADS` | `4` | 推理线程数，调小更省 CPU |
| 模型目录 | `~/.ollama/models` | 自动扫描里面的 GGUF 权重 |

默认会**过滤掉 embedding / 视觉类模型**（如 `nomic-embed`、`minicpm-v`、`clip`），只暴露聊天模型，
避免流水线误调到非文本模型而崩溃。

## 接口示例

```bash
# 列出模型
curl http://127.0.0.1:11434/api/tags

# 生成（流式 NDJSON，每行一个 JSON）
curl -X POST http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:3b","prompt":"你好","stream":false}'
```

## 目录结构

```
tongyu-engine/
├── 同宇引擎.py        # 引擎本体（llama-cpp-python + pystray + 兼容 API）
├── TongyuEngine.spec  # PyInstaller 打包配置
├── requirements.txt
├── README.md
└── LICENSE
```

## 许可证

[MIT](LICENSE) —— 可自由使用、修改、商用，也可基于此上架你自己的应用商店产品。

---

## 知识星球 · 零基础AI造应用·同宇圈

想系统学「用 AI 造应用 / 做 AI 有声小说 / 搭本地模型」？加入我的知识星球，看完整教程 + 社群答疑 + 源码更新通知：

https://wx.zsxq.com/group/48882488185118

出品：AI 有声·同宇出品。本项目基于 MIT 许可证开源，可自由使用、修改、商用、上架。
