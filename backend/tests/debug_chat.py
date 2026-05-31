import subprocess
import sys
import time
import os
import urllib.request
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(ROOT, "..", ".venv", "Scripts", "python.exe")
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"

def wait_for(url, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    log_path = os.path.join(ROOT, "tests", "debug_chat_server.log")
    logf = open(log_path, "w", encoding="utf-8")

    print("[Debug] Starting server on port", PORT)
    proc = subprocess.Popen(
        [VENV_PY, "-u", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
    )

    try:
        if not wait_for(f"{BASE}/health", timeout=30):
            print("[Debug] Server startup timeout!")
            logf.flush()
            return 1
        print("[Debug] Server ready")

        # Test chat
        print("[Debug] Testing /chat ...")
        req = urllib.request.Request(
            f"{BASE}/api/v1/chat",
            data=json.dumps({"user_id": 999, "message": "有什么推荐的菜品？", "cart": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode("utf-8"))
            print("[Debug] Status:", resp.status)
            print("[Debug] Response:", data.get("response", "")[:200])
            print("[Debug] Cart:", data.get("cart", []))
        except urllib.error.HTTPError as e:
            print("[Debug] HTTP Error:", e.code, e.read().decode("utf-8")[:200])
        except Exception as e:
            print("[Debug] Error:", type(e).__name__, str(e)[:200])

        time.sleep(1)
        logf.flush()

        # Print server log
        print("\n[Debug] Server log tail:")
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print("  ", line.rstrip())

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
        logf.close()

if __name__ == "__main__":
    sys.exit(main())
