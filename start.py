#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点餐机器人一键启动脚本
启动后端 FastAPI + 前端 Vue3，并自动打开浏览器
"""

import os
import sys
import time
import signal
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

# 颜色输出
class Colors:
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    DARK_GRAY = "\033[90m"
    RESET = "\033[0m"


def print_banner():
    print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.CYAN}    智能点餐机器人 - 一键启动脚本{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
    print()


def kill_port(port: int):
    """Windows 下查找并结束占用指定端口的进程"""
    if sys.platform != "win32":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano", "|", "findstr", f":{port}"],
            capture_output=True,
            text=True,
            shell=True,
        )
        pids = set()
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    pass
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
                print(f"{Colors.DARK_GRAY}       已清理占用端口 {port} 的进程 (PID: {pid}){Colors.RESET}")
            except Exception:
                pass
    except Exception:
        pass


def log_stream(proc, name, color):
    """读取子进程输出并打印"""
    try:
        for line in proc.stdout:
            print(f"{color}[{name}]{Colors.RESET} {line.rstrip()}")
    except Exception:
        pass


def check_command(cmd: str) -> bool:
    """检查系统命令是否可用"""
    return shutil.which(cmd) is not None


def start_backend(root: Path):
    """启动后端服务"""
    backend_dir = root / "backend"
    print(f"{Colors.GREEN}[1/3] 正在启动后端服务 (FastAPI + MySQL)...{Colors.RESET}")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    t = threading.Thread(target=log_stream, args=(proc, "后端", Colors.GREEN), daemon=True)
    t.start()
    return proc


def start_frontend(root: Path):
    """启动前端服务"""
    frontend_dir = root / "frontend"
    print(f"{Colors.GREEN}[2/3] 正在启动前端服务 (Vue3 + Vite)...{Colors.RESET}")

    if sys.platform == "win32":
        proc = subprocess.Popen(
            "npm run dev",
            cwd=str(frontend_dir),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        proc = subprocess.Popen(
            [shutil.which("npm") or "npm", "run", "dev"],
            cwd=str(frontend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    t = threading.Thread(target=log_stream, args=(proc, "前端", Colors.YELLOW), daemon=True)
    t.start()
    return proc


def wait_for_url(url: str, timeout: int = 30) -> bool:
    """等待服务就绪"""
    import urllib.request
    import urllib.error

    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.URLError:
            time.sleep(0.5)
    return False


def main():
    print_banner()

    # 环境检查
    if not check_command("python"):
        print(f"{Colors.RED}[错误] 未找到 Python，请确保 Python 3.10+ 已安装并加入 PATH{Colors.RESET}")
        sys.exit(1)
    if not check_command("node"):
        print(f"{Colors.RED}[错误] 未找到 Node.js，请确保 Node.js 18+ 已安装并加入 PATH{Colors.RESET}")
        sys.exit(1)

    root = Path(__file__).parent.resolve()
    backend_proc = None
    frontend_proc = None

    def cleanup(*args):
        print(f"\n{Colors.MAGENTA}正在停止所有服务...{Colors.RESET}")
        if backend_proc:
            backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        time.sleep(1)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, cleanup)

    try:
        # 清理残留端口
        print(f"{Colors.DARK_GRAY}       清理残留进程...{Colors.RESET}")
        kill_port(8000)
        kill_port(5173)
        time.sleep(1)

        # 启动后端
        backend_proc = start_backend(root)
        print(f"{Colors.DARK_GRAY}       等待后端就绪 (http://127.0.0.1:8000)...{Colors.RESET}")
        if not wait_for_url("http://127.0.0.1:8000/", timeout=30):
            print(f"{Colors.RED}       后端启动超时，请检查上方日志{Colors.RESET}")
            cleanup()

        # 启动前端
        frontend_proc = start_frontend(root)
        print(f"{Colors.DARK_GRAY}       等待前端就绪 (http://localhost:5173)...{Colors.RESET}")
        if not wait_for_url("http://localhost:5173/", timeout=60):
            print(f"{Colors.RED}       前端启动超时，请检查上方日志{Colors.RESET}")
            cleanup()

        # 打开浏览器
        print(f"{Colors.GREEN}[3/3] 正在打开浏览器...{Colors.RESET}")
        webbrowser.open("http://localhost:5173")

        print()
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print(f"{Colors.GREEN} 启动完成！{Colors.RESET}")
        print(f"{Colors.YELLOW} 前端地址: http://localhost:5173{Colors.RESET}")
        print(f"{Colors.YELLOW} 后端地址: http://127.0.0.1:8000/docs{Colors.RESET}")
        print(f"{Colors.MAGENTA} 按 Ctrl+C 停止所有服务{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print()

        # 保持运行并监控子进程
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print(f"{Colors.RED}后端服务已退出 (code: {backend_proc.returncode}){Colors.RESET}")
                break
            if frontend_proc.poll() is not None:
                print(f"{Colors.RED}前端服务已退出 (code: {frontend_proc.returncode}){Colors.RESET}")
                break

    except Exception as e:
        print(f"{Colors.RED}发生错误: {e}{Colors.RESET}")
        cleanup()


if __name__ == "__main__":
    main()
