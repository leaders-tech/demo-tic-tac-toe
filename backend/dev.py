"""Run the backend with simple auto-reload for local development.

Edit this file when reload rules, watched files, or restart behavior changes.
Copy this file only when you add another small local dev helper process.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
WATCH_DIRS = [ROOT_DIR / "backend"]
WATCH_FILES = [ROOT_DIR / ".env", ROOT_DIR / "pyproject.toml"]
IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def iter_watched_files() -> list[Path]:
    files: list[Path] = []
    for watch_dir in WATCH_DIRS:
        for path in watch_dir.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            files.append(path)
    for path in WATCH_FILES:
        if path.exists():
            files.append(path)
    return sorted(set(files))


def snapshot_files() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    for path in iter_watched_files():
        snapshot[path] = path.stat().st_mtime_ns
    return snapshot


def start_backend() -> subprocess.Popen[bytes]:
    print("Starting backend server...")
    return subprocess.Popen(
        [sys.executable, "-m", "backend.main"],
        cwd=ROOT_DIR,
        env=os.environ.copy(),
    )


def stop_backend(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_reloader() -> int:
    process = start_backend()
    previous = snapshot_files()

    try:
        while True:
            time.sleep(0.7)

            if process.poll() is not None:
                print("Backend process stopped. Restarting...")
                process = start_backend()
                previous = snapshot_files()
                continue

            current = snapshot_files()
            if current != previous:
                print("Code change detected. Restarting backend...")
                stop_backend(process)
                process = start_backend()
                previous = current
    except KeyboardInterrupt:
        print("\nStopping backend reloader...")
        stop_backend(process)
        return 0


if __name__ == "__main__":
    raise SystemExit(run_reloader())
