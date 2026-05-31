import subprocess
import sys
import time
import os

BASE_URL = "http://127.0.0.1:8000"
MAX_WAIT = 30


def wait_for_service(url, timeout=30):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(root, "..", ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # 清理已有端口占用
    try:
        subprocess.run("netstat -ano | findstr :8000 | findstr LISTENING", shell=True, capture_output=True)
    except Exception:
        pass

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print("[Integration] Starting FastAPI server...")
    log_path = os.path.join(root, "tests", "server_int.log")
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=root,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    try:
        health_url = f"{BASE_URL}/health"
        if wait_for_service(health_url, timeout=MAX_WAIT):
            print("[Integration] Server is ready!")
        else:
            print("[Integration] Server startup timeout!")
            log_file.flush()
            return 1

        print("[Integration] Running test_all.py...")
        test_script = os.path.join(root, "tests", "test_all.py")
        result = subprocess.run([venv_python, test_script], cwd=root, env=env)
        return result.returncode

    finally:
        print("[Integration] Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        print("[Integration] Server stopped.")


if __name__ == "__main__":
    sys.exit(main())
