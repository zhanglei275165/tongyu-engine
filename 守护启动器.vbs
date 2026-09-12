Set WshShell = CreateObject("WScript.Shell")

' 让同宇引擎跑在已装好 llama-cpp-python 的虚拟环境里
WshShell.Environment("User")("TY_PYTHON") = "F:\同宇AI\venv\Scripts\python.exe"
' 直连 127.0.0.1，禁止走系统代理（避免守护探测被代理拦截误判）
WshShell.Environment("User")("no_proxy") = "127.0.0.1,localhost"
WshShell.Environment("User")("HTTP_PROXY") = ""
WshShell.Environment("User")("HTTPS_PROXY") = ""

Py = "F:\同宇AI\venv\Scripts\python.exe"
Script = "F:\opensource\tongyu-engine\tongyu_engine_guard.py"

' 0 = 隐藏窗口后台运行，双击即用、无黑框
WshShell.Run Chr(34) & Py & Chr(34) & " " & Chr(34) & Script & Chr(34), 0, False
