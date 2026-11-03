#!/usr/bin/env python3
"""SameSame: one command to set up and run everything, on macOS and Windows.

    python start.py            # dev: FastAPI :8000 + Vite :5173 (hot reload)
    python start.py --demo     # stage: build the frontend once, serve everything from FastAPI :8000
    python start.py --rebuild  # re-run the data/model pipeline (and frontend build in --demo)
    python start.py --test     # run backend tests and exit

First run needs network (pip, npm, model download). After that it runs fully offline.
Stdlib only: this file runs before the virtualenv exists.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
WIN = os.name == "nt"
VPY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
API_PORT, UI_PORT = 8000, 5173


def say(msg):
    print(f"\033[36m[samesame]\033[0m {msg}" if not WIN else f"[samesame] {msg}", flush=True)


def run(cmd, cwd=ROOT, **kw):
    say(" ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True, **kw)


def digest(*files):
    h = hashlib.sha256()
    for f in files:
        h.update(Path(f).read_bytes() if Path(f).exists() else b"")
    return h.hexdigest()


def stamp_ok(stamp: Path, value: str):
    return stamp.exists() and stamp.read_text() == value


def ensure_python():
    if sys.version_info < (3, 11):
        sys.exit(f"SameSame needs Python 3.11+; this is {sys.version.split()[0]}.")
    if not VPY.exists():
        say("creating virtualenv .venv")
        run([sys.executable, "-m", "venv", VENV])
    req = BACKEND / "requirements.txt"
    stamp, want = VENV / ".req-stamp", digest(req)
    if stamp_ok(stamp, want):
        return
    run([VPY, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    run([VPY, "-m", "pip", "install", "torch", "--index-url", TORCH_CPU_INDEX, "-q"])
    run([VPY, "-m", "pip", "install", "-r", req, "-q"])
    if not lightgbm_ok() and sys.platform == "darwin":
        patch_lightgbm_libomp()
    if not lightgbm_ok():
        say("WARNING: lightgbm failed to import. On macOS run: brew install libomp")
    stamp.write_text(want)


def lightgbm_ok():
    return subprocess.run([str(VPY), "-c", "import lightgbm"], capture_output=True).returncode == 0


def patch_lightgbm_libomp():
    """macOS without Homebrew libomp: point the venv's lib_lightgbm at the libomp that the
    scikit-learn wheel already bundles. Touches only files inside .venv."""
    code = ("import pathlib, sklearn, sysconfig; sp = pathlib.Path(sysconfig.get_paths()['purelib']);"
            "print(sp / 'lightgbm/lib/lib_lightgbm.dylib'); print(pathlib.Path(sklearn.__file__).parent / '.dylibs')")
    out = subprocess.run([str(VPY), "-c", code], capture_output=True, text=True)
    if out.returncode != 0:
        return
    lib, omp_dir = out.stdout.split("\n")[:2]
    if not (Path(omp_dir) / "libomp.dylib").exists():
        return
    say("libomp not found; linking lightgbm to scikit-learn's bundled libomp (venv only)")
    subprocess.run(["install_name_tool", "-add_rpath", omp_dir, lib], capture_output=True)
    subprocess.run(["codesign", "--force", "-s", "-", lib], capture_output=True)


def ensure_node():
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Node.js 18+ is required (npm not found on PATH). Install from nodejs.org.")
    stamp, want = FRONTEND / "node_modules" / ".pkg-stamp", digest(FRONTEND / "package.json", FRONTEND / "package-lock.json")
    if not stamp_ok(stamp, want):
        run([npm, "install", "--no-fund", "--no-audit"], cwd=FRONTEND)
        stamp.write_text(want)
    return npm


def ensure_pipeline(force):
    if force or not (ROOT / "data" / "build" / "manifest.json").exists():
        run([VPY, "-m", "samesame.pipeline"], cwd=BACKEND)


def ensure_frontend_build(npm, force):
    dist = FRONTEND / "dist" / "index.html"
    newest_src = max(p.stat().st_mtime for p in (FRONTEND / "src").rglob("*") if p.is_file())
    if force or not dist.exists() or dist.stat().st_mtime < newest_src:
        run([npm, "run", "build"], cwd=FRONTEND)


def wait_for(url, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="single-port stage mode (prebuilt frontend)")
    ap.add_argument("--rebuild", action="store_true", help="re-run pipeline and frontend build")
    ap.add_argument("--skip-install", action="store_true", help="offline: do not touch pip/npm")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--test", action="store_true", help="run backend tests and exit")
    args = ap.parse_args()

    if not args.skip_install:
        ensure_python()
    npm = shutil.which("npm") if args.skip_install else ensure_node()
    ensure_pipeline(args.rebuild)

    if args.test:
        sys.exit(subprocess.run([str(VPY), "-m", "pytest", "-q"], cwd=BACKEND).returncode)

    procs = []
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    api_cmd = [str(VPY), "-m", "uvicorn", "samesame.api.app:app", "--host", "127.0.0.1", "--port", str(API_PORT)]
    if args.demo:
        ensure_frontend_build(npm, args.rebuild)
        procs.append(subprocess.Popen(api_cmd, cwd=BACKEND, env=env))
        url = f"http://localhost:{API_PORT}"
    else:
        procs.append(subprocess.Popen(api_cmd + ["--reload"], cwd=BACKEND, env=env))
        procs.append(subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND, env=env))
        url = f"http://localhost:{UI_PORT}"

    try:
        if not wait_for(f"http://127.0.0.1:{API_PORT}/api/meta"):
            say(f"backend did not come up on :{API_PORT} (port in use?)")
        elif args.demo or wait_for(url):
            say(f"SameSame is running at {url}  (Ctrl+C to stop)")
            if not args.no_browser:
                webbrowser.open(url)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        say("stopped")


if __name__ == "__main__":
    main()
