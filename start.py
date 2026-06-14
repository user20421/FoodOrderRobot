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

# 修复 Windows 控制台中文输出乱码
if sys.platform == "win32":
    os.system("chcp 65001 >nul")
    # 同时设置 Python 标准 IO 编码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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
    print(f"{color}[启动器]{Colors.RESET} {msg}", flush=True)


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


def _port_pids_windows(port):
    """Windows: 返回占用指定端口的进程PID列表"""
    pids = set()
    try:
        # 使用 netstat 查找监听端口的进程
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, shell=False, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    try:
                        pids.add(int(parts[-1]))
                    except ValueError:
                        continue
    except Exception:
        pass
    return pids


def _port_pids_unix(port):
    """Linux/macOS: 返回占用指定端口的进程PID列表"""
    pids = set()
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, shell=False
        )
        for line in result.stdout.splitlines():
            try:
                pids.add(int(line.strip()))
            except ValueError:
                continue
    except Exception:
        pass
    return pids


def _safe_process_names():
    """可以安全终止的进程名关键字（小写）"""
    return {"python", "python.exe", "uvicorn", "node", "node.exe", "npm", "npm.cmd", "vite"}


def _process_name_windows(pid):
    """获取 Windows 进程名"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, shell=False, encoding="utf-8", errors="ignore"
        )
        first = result.stdout.strip().splitlines()[0]
        # CSV 格式: "name.exe","123",...
        if first.startswith('"'):
            return first.split('","')[0].strip('"').lower()
    except Exception:
        pass
    return ""


def _process_name_unix(pid):
    """获取 Unix 进程名"""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True, text=True, shell=False
        )
        return result.stdout.strip().lower()
    except Exception:
        pass
    return ""


def kill_port(port):
    """清理端口占用，只终止安全的进程（python/uvicorn/node/npm/vite）"""
    system = platform.system()
    pids = _port_pids_windows(port) if system == "Windows" else _port_pids_unix(port)
    if not pids:
        return

    safe_names = _safe_process_names()
    killed = []
    for pid in pids:
        if pid == os.getpid():
            continue
        name = _process_name_windows(pid) if system == "Windows" else _process_name_unix(pid)
        if not any(s in name for s in safe_names):
            log(f"端口 {port} 被非本项目的进程 {name}(PID={pid}) 占用，跳过清理", Colors.YELLOW)
            continue
        try:
            if system == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True)
            killed.append(pid)
        except Exception:
            pass
    if killed:
        log(f"已清理端口 {port} 的进程: PID={killed}")


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


def find_venv_python(root: Path):
    """查找虚拟环境 Python"""
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python",
    ]
    for vp in candidates:
        if vp.exists():
            return str(vp)
    return None


def build_frontend(frontend_dir: Path):
    """生产模式：构建前端"""
    log("生产模式：构建前端...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        shell=True if os.name == "nt" else False,
        capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    if result.returncode != 0:
        log("前端构建失败：", Colors.RED)
        log(result.stdout or result.stderr or "无输出", Colors.RED)
        return False
    log("前端构建完成", Colors.GREEN)
    return True


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

    # 生产模式必须安装 Node
    if is_prod and not has_node:
        log("生产模式需要 Node.js 来构建前端", Colors.RED)
        sys.exit(1)

    # 确定路径
    root = Path(__file__).parent.resolve()
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"

    # 检查目录存在
    if not backend_dir.exists():
        log(f"后端目录不存在: {backend_dir}", Colors.RED)
        sys.exit(1)
    if not is_prod and not frontend_dir.exists():
        log(f"前端目录不存在: {frontend_dir}", Colors.YELLOW)
        has_node = False

    # 查找虚拟环境
    venv_python = find_venv_python(root)
    python_cmd = venv_python or sys.executable
    if venv_python:
        log(f"使用虚拟环境: {venv_python}")

    processes = []

    try:
        # 生产模式：构建前端
        if is_prod:
            dist_dir = frontend_dir / "dist"
            # 如果 dist 不存在或需要重新构建，执行 npm run build
            if not dist_dir.exists():
                if not build_frontend(frontend_dir):
                    sys.exit(1)
            else:
                log("生产模式：使用已有的前端 dist 目录")

        # 清理端口
        kill_port(BACKEND_PORT)
        if not is_prod:
            kill_port(FRONTEND_PORT)

        # 启动后端
        log("启动 FastAPI 后端...")
        backend_cmd = [
            python_cmd, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(BACKEND_PORT),
        ]
        if not is_prod:
            backend_cmd.append("--reload")

        backend_env = os.environ.copy()
        # 生产模式告诉后端托管静态文件
        if is_prod:
            backend_env["SERVE_STATIC"] = "true"
            backend_env["STATIC_DIR"] = str(frontend_dir / "dist")

        creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=str(backend_dir),
            env=backend_env,
            creationflags=creationflags,
        )
        processes.append(("backend", backend_proc))
        log(f"后端进程 PID={backend_proc.pid}")

        # 等待后端就绪
        if wait_for_service(BACKEND_URL + "/health", timeout=30):
            log(f"后端已就绪: {BACKEND_URL}", Colors.GREEN)
        else:
            # 检查进程是否已退出
            if backend_proc.poll() is not None:
                log(f"后端进程已退出 (code={backend_proc.returncode})，启动失败", Colors.RED)
            else:
                log("后端启动超时，请手动检查", Colors.YELLOW)
            return

        # 启动前端
        if not is_prod and has_node:
            log("启动 Vue 前端...")
            frontend_cmd = ["npm", "run", "dev"]
            frontend_proc = subprocess.Popen(
                frontend_cmd,
                cwd=str(frontend_dir),
                shell=True if os.name == "nt" else False,
                creationflags=creationflags,
            )
            processes.append(("frontend", frontend_proc))
            log(f"前端进程 PID={frontend_proc.pid}")

            if wait_for_service(FRONTEND_URL, timeout=30):
                log(f"前端已就绪: {FRONTEND_URL}", Colors.GREEN)
                open_browser(FRONTEND_URL)
            else:
                if frontend_proc.poll() is not None:
                    log(f"前端进程已退出 (code={frontend_proc.returncode})，启动失败", Colors.YELLOW)
                else:
                    log("前端启动超时", Colors.YELLOW)
        elif is_prod:
            log("生产模式：前端由后端托管静态文件")

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
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                log(f"已停止 {name} (PID={proc.pid})")
            except Exception:
                pass

        # 再次清理端口
        kill_port(BACKEND_PORT)
        if not is_prod:
            kill_port(FRONTEND_PORT)
        log("所有服务已停止", Colors.GREEN)


if __name__ == "__main__":
    main()
