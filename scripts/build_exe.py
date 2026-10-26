import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRY_POINT = BASE_DIR / "web" / "app.py"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

def run_pyinstaller():
    """
    Compiles AI-Telefonist into a lightweight (~45MB) standalone executable.
    Embeds Python runtime, dependencies, and web templates/static assets.
    EXCLUDES the heavy models/ and bin/llama/ directories to prevent Windows PE limits.
    """
    print("==================================================")
    print(" AI-Telefonist • PyInstaller Compilation")
    print("==================================================")

    # Validate entry point
    if not ENTRY_POINT.exists():
        print(f"Error: Entry point {ENTRY_POINT} not found.")
        sys.exit(1)

    # Prepare data inclusions for templates & static
    web_dir = BASE_DIR / "web"
    templates_src = web_dir / "templates"
    static_src = web_dir / "static"

    # PyInstaller add-data syntax: source;destination (Windows uses ;)
    add_data_templates = f"{templates_src};web/templates"
    add_data_static = f"{static_src};web/static"

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name", "ai-telefonist",
        "--add-data", add_data_templates,
        "--add-data", add_data_static,
        # Hidden imports needed for dynamic imports & async packages
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "engineio.async_drivers.asgi",
        str(ENTRY_POINT)
    ]

    print("Executing command:\n", " ".join(pyinstaller_cmd))
    result = subprocess.run(pyinstaller_cmd, cwd=str(BASE_DIR))

    if result.returncode == 0:
        exe_path = DIST_DIR / "ai-telefonist.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("==================================================")
            print(f" SUCCESS! Binary created: {exe_path}")
            print(f" Binary Size: {size_mb:.2f} MB")
            print(" Model weights and llama-server excluded (handled by installer).")
            print("==================================================")
        else:
            print("Compilation succeeded but output executable was not found.")
    else:
        print(f"Compilation failed with exit code: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    run_pyinstaller()
