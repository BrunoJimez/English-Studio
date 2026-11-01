"""Windows desktop entry point: start the local server once and open an app window."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8765"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def healthy():
    try:
        with urllib.request.urlopen(URL + "/api/health", timeout=2) as response:
            return json.load(response).get("app") == "english-studio"
    except Exception:
        return False


def main():
    if not healthy():
        python = ROOT / ".venv" / "Scripts" / "python.exe"
        if not python.exists():
            raise RuntimeError("Execute Instalar.ps1 antes de abrir o English Studio.")
        (ROOT / "data").mkdir(exist_ok=True)
        with (ROOT / "data" / "server.log").open("a", encoding="utf-8") as log:
            subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
                             cwd=ROOT, stdout=log, stderr=log, creationflags=FLAGS)
        for _ in range(80):
            if healthy():
                break
            time.sleep(.25)
        else:
            raise RuntimeError("O estúdio não iniciou. Consulte data/server.log. A porta 8765 pode estar ocupada.")
    # Start Ollama's background service only if it is not already listening.
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).close()
    except Exception:
        ollama = shutil.which("ollama")
        if ollama:
            with (ROOT / "data" / "ollama.log").open("a") as log:
                subprocess.Popen([ollama, "serve"], stdout=log, stderr=log, creationflags=FLAGS)
    candidates = [Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
                  Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe"]
    for browser in candidates:
        if browser.exists():
            startup = None
            if os.name == "nt":
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 1  # Show the interactive app even when the launcher is hidden.
            subprocess.Popen([str(browser), "--app=" + URL, "--window-size=1440,960", "--no-first-run", "--no-default-browser-check"], startupinfo=startup)
            break
    else:
        webbrowser.open(URL)


if __name__ == "__main__":
    mutex = None
    try:
        if os.name == "nt":
            kernel = ctypes.windll.kernel32
            kernel.CreateMutexW.restype = ctypes.c_void_p
            mutex = kernel.CreateMutexW(None, False, "Local\\EnglishStudioLauncher")
            wait = kernel.WaitForSingleObject(ctypes.c_void_p(mutex), 30000)
            if wait not in (0, 0x80):
                raise RuntimeError("Outra janela está iniciando o estúdio. Aguarde e tente novamente.")
        main()
    except Exception as exc:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, str(exc), "English Studio", 0x10)
        else:
            raise
    finally:
        if mutex:
            ctypes.windll.kernel32.ReleaseMutex(ctypes.c_void_p(mutex))
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
