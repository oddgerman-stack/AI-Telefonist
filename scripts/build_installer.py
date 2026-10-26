import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
ISS_PATH = SCRIPTS_DIR / "installer.iss"
DIST_DIR = BASE_DIR / "dist"
EXE_PATH = DIST_DIR / "ai-telefonist.exe"

POSSIBLE_ISCC_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    r"C:\Program Files\Inno Setup 5\ISCC.exe",
]

def find_iscc() -> str:
    """Locates Inno Setup Compiler executable."""
    cmd = shutil.which("iscc")
    if cmd:
        return cmd

    for path in POSSIBLE_ISCC_PATHS:
        if os.path.exists(path):
            return path

    return ""

def build_installer():
    """
    Compiles AI-Telefonist-Installer.exe using Inno Setup.
    Packages ai-telefonist.exe, models/, and bin/llama/ with max LZMA2 compression.
    """
    print("==================================================")
    print(" AI-Telefonist • Inno Setup Installer Builder")
    print("==================================================")

    # 1. Ensure PyInstaller build exists
    if not EXE_PATH.exists():
        print(f"[Build] {EXE_PATH.name} not found. Running build_exe.py first...")
        build_exe_script = SCRIPTS_DIR / "build_exe.py"
        res = subprocess.run([sys.executable, str(build_exe_script)], cwd=str(BASE_DIR))
        if res.returncode != 0:
            print("[Error] Failed to build PyInstaller executable.")
            sys.exit(1)

    # 2. Locate ISCC
    iscc_path = find_iscc()
    if not iscc_path:
        print("\n[Notice] Inno Setup Compiler (ISCC.exe) was not found on your system.")
        print("To build the single-file setup installer (AI-Telefonist-Installer.exe):")
        print("1. Download Inno Setup 6: https://jrsoftware.org/isdl.php")
        print(f"2. Run: ISCC.exe {ISS_PATH}")
        print("\nThe standalone portable executable is already available at dist/ai-telefonist.exe.")
        return

    print(f"[Inno Setup] Located compiler: {iscc_path}")
    print(f"[Inno Setup] Compiling {ISS_PATH.name}...")

    result = subprocess.run([iscc_path, str(ISS_PATH)], cwd=str(SCRIPTS_DIR))
    if result.returncode == 0:
        installer_path = DIST_DIR / "AI-Telefonist-Installer.exe"
        print("==================================================")
        print(" SUCCESS! Installer compiled successfully.")
        print(f" Installer Package: {installer_path}")
        print(" Max LZMA2 compression applied.")
        print(" Clean uninstallation & process termination keys added.")
        print("==================================================")
    else:
        print(f"[Error] Inno Setup compilation failed with code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    build_installer()
