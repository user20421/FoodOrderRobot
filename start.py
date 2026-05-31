#!/usr/bin/env python3
"""
智能点餐机器人 - 一键启动脚本
支持开发模式（前后端同时启动）和生产模式
"""
import os
import sys
import time
import signal
import subprocess
import platform
from pathlib import Path

# 配置
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

# 颜色输出
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def log(msg, color=Colors.BLUE):
    print(f"{color}[启动器]{Colors.RESET} {msg}")


def check_python():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        log(f"需要 Python 3.10+，当前 {version.major}.{version.minor}", Colors.RED)
        return False
    return True


def check_node():
    """检查Node.js"""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"Node.js: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    log("未检测到 Node.js，前端将无法启动", Colors.YELLOW)
    return False


def kill_port(port):
    """清理端口占用"""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["netstat", "-ano", "|", "findstr", f":{port}"],
                capture_output=True, text=True, shell=True
            )
            for line in result.stdout.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                        log(f"已清理端口 {port} 的进程 PID={pid}")
        else:
            subprocess.run(
                f"lsof -ti:{port} | xargs kill -9 2>/dev/null",
                shell=True, capture_output=True
            )
    except Exception:
        pass


def wait_for_service(url, timeout=30):
    """等待服务就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def open_browser(url):
    """打开浏览器"""
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    is_prod = "--prod" in args

    log("=" * 50)
    log("智能点餐机器人 启动中...")
    log("=" * 50)

    # 环境检查
    if not check_python():
        sys.exit(1)
    has_node = check_node()

    # 清理端口
    kill_port(BACKEND_PORT)
    if not is_prod:
        kill_port(FRONTEND_PORT)

    # 确定路径
    root = Path(__file__).parent
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"

    # 检查虚拟环境
    venv_python = None
    if os.name == "nt":  # Windows
        venv_paths = [
            root / ".venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python.exe",
        ]
    else:
        venv_paths = [
            root / ".venv" / "bin" / "python",
            root / "venv" / "bin" / "python",
        ]

    for vp in venv_paths:
        if vp.exists():
            venv_python = str(vp)
            log(f"使用虚拟环境: {venv_python}")
            break

    python_cmd = venv_python or sys.executable

    processes = []

    try:
        # 启动后端
        log("启动 FastAPI 后端...")
        backend_cmd = [
            python_cmd, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(BACKEND_PORT),
            "--reload" if not is_prod else "",
        ]
        backend_cmd = [c for c in backend_cmd if c]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=str(backend_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        processes.append(("backend", backend_proc))
        log(f"后端进程 PID={backend_proc.pid}")

        # 等待后端就绪
        if wait_for_service(BACKEND_URL + "/health", timeout=30):
            log(f"后端已就绪: {BACKEND_URL}", Colors.GREEN)
        else:
            log("后端启动超时，请手动检查", Colors.YELLOW)

        # 启动前端
        if not is_prod and has_node:
            log("启动 Vue 前端...")
            frontend_cmd = ["npm", "run", "dev"]
            frontend_proc = subprocess.Popen(
                frontend_cmd,
                cwd=str(frontend_dir),
                shell=True if os.name == "nt" else False,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
            processes.append(("frontend", frontend_proc))
            log(f"前端进程 PID={frontend_proc.pid}")

            if wait_for_service(FRONTEND_URL, timeout=30):
                log(f"前端已就绪: {FRONTEND_URL}", Colors.GREEN)
                open_browser(FRONTEND_URL)
            else:
                log("前端启动超时", Colors.YELLOW)
        elif is_prod:
            log("生产模式：前端由后端托管静态文件")
            # 确保dist存在
            dist_dir = frontend_dir / "dist"
            if not dist_dir.exists():
                log("前端 dist 目录不存在，请先构建: npm run build", Colors.YELLOW)

        log("=" * 50)
        log("所有服务已启动！", Colors.GREEN)
        if not is_prod:
            log(f"前端访问: {FRONTEND_URL}")
        log(f"后端API: {BACKEND_URL}")
        log(f"API文档: {BACKEND_URL}/docs")
        log("按 Ctrl+C 停止所有服务")
        log("=" * 50)

        # 保持运行
        while True:
            time.sleep(1)
            # 检查进程是否还在运行
            for name, proc in processes:
                if proc.poll() is not None:
                    log(f"{name} 进程已退出 (code={proc.returncode})", Colors.YELLOW)
                    return

    except KeyboardInterrupt:
        log("\n收到停止信号，正在关闭服务...")
    finally:
        for name, proc in processes:
            try:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.terminate()
                    proc.wait(timeout=5)
                log(f"已停止 {name} (PID={proc.pid})")
            except Exception:
                pass

        # 再次清理端口
        kill_port(BACKEND_PORT)
        kill_port(FRONTEND_PORT)
        log("所有服务已停止", Colors.GREEN)


if __name__ == "__main__":
    main()
