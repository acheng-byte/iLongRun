"""
iLongRun v0.9.0 Windows 兼容补丁
应用位置: ~/copilot-longrun/scripts/
"""
import re, shutil
from pathlib import Path

SCRIPTS = Path.home() / "copilot-longrun" / "scripts"

def patch(name, fn):
    f = SCRIPTS / name
    if not f.exists():
        print(f"SKIP (not found): {name}")
        return
    shutil.copy2(f, str(f) + ".bak")
    src = f.read_text(encoding="utf-8")
    patched = fn(src)
    if patched == src:
        print(f"NO CHANGE: {name}")
    else:
        f.write_text(patched, encoding="utf-8")
        print(f"PATCHED: {name}")

# ─── 1. launch_ilongrun_supervisor.py ────────────────────────────────────────

def patch_supervisor(src):
    # 1a. build_command: 去掉不兼容 flags，加 --add-dir workspace
    OLD_BUILD = '''\
def build_command(args, skill_ref: str, payload: str, model: str) -> list[str]:
    cmd = [args.copilot_bin]
    for item in args.plugin_arg:
        cmd.extend(["--plugin-dir", item])
    if args.mode in {"run", "resume"}:
        cmd.extend(["--autopilot", "--yolo", "--no-ask-user", "--max-autopilot-continues", str(args.max_continues)])
    else:
        cmd.extend(["--yolo", "--no-ask-user"])
    cmd.extend(["--model", model, "-p", f"{skill_ref} {payload}".strip()])
    return cmd'''
    NEW_BUILD = '''\
def build_command(args, skill_ref: str, payload: str, model: str) -> list[str]:
    cmd = [args.copilot_bin]
    for item in args.plugin_arg:
        cmd.extend(["--plugin-dir", item])
    # Windows: --add-dir grants file write permission without --dangerously-skip-permissions
    cmd.extend(["--add-dir", str(Path(os.getcwd()))])
    if args.mode in {"run", "resume"}:
        cmd.extend(["--max-turns", str(args.max_continues)])
    cmd.extend(["--model", model, "-p", f"{skill_ref} {payload}".strip()])
    return cmd'''

    if OLD_BUILD in src:
        src = src.replace(OLD_BUILD, NEW_BUILD)
        print("  build_command patched")
    else:
        print("  WARNING: build_command pattern not found, manual check needed")

    # 1b. run_and_stream: Windows bash wrapper + UTF-8 + temp file for payload
    OLD_STREAM = '''\
def run_and_stream(cmd: list[str], cwd: Path, env_patch: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if env_patch:
        env.update(env_patch)
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )'''

    NEW_STREAM = '''\
def run_and_stream(cmd: list[str], cwd: Path, env_patch: dict[str, str] | None = None) -> tuple[int, str]:
    import sys as _sys, tempfile as _tmp, shlex as _shlex
    env = os.environ.copy()
    if env_patch:
        env.update(env_patch)
    if _sys.platform == "win32":
        _bash = env.get("CLAUDE_CODE_GIT_BASH_PATH", "")
        if _bash and Path(_bash).is_file():
            def _w2b(p: str) -> str:
                p = str(p).replace("\\\\", "/").replace("\\\\\\\\", "/")
                if len(p) >= 2 and p[1] == ":":
                    p = "/" + p[0].lower() + p[2:]
                return p
            i = cmd.index("-p") if "-p" in cmd else -1
            if i >= 0 and i + 1 < len(cmd):
                pf = _tmp.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
                pf.write(cmd[i + 1])
                pf.close()
                rest = cmd[:i] + cmd[i + 2:]
                cs = " ".join(_shlex.quote(_w2b(str(c))) for c in rest)
                sf = _tmp.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8")
                sf.write("#!/usr/bin/env bash\\n" + cs + ' -p "$(cat ' + _shlex.quote(_w2b(pf.name)) + ')"\\n')
                sf.close()
                cmd = [_bash, _w2b(sf.name)]
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )'''

    if OLD_STREAM in src:
        src = src.replace(OLD_STREAM, NEW_STREAM)
        print("  run_and_stream patched")
    else:
        print("  WARNING: run_and_stream pattern not found")

    return src

# ─── 2. render_ilongrun_install_board.py ─────────────────────────────────────

def patch_install_board(src):
    old = "    if os.uname().sysname == \"Darwin\":"
    new = "    if getattr(os, 'uname', lambda: type('', (), {'sysname': ''})()).sysname == \"Darwin\":"
    if old in src:
        src = src.replace(old, new)
        print("  os.uname() patched")
    else:
        print("  WARNING: os.uname() pattern not found")
    return src

# ─── 3. selftest_ilongrun.py: prepare_ilongrun_run.py Windows 兼容 ─────────────

def patch_selftest(src):
    # Fix subprocess call for Windows - use python to run .py files
    old = "        subprocess.run(\n            args,\n"
    new = "        _args = args\n        if __import__('sys').platform == 'win32' and str(_args[0]).endswith('.py'):\n            _args = [__import__('sys').executable] + list(_args[1:])\n        subprocess.run(\n            _args,\n"
    if old in src:
        src = src.replace(old, new)
        print("  selftest subprocess patched")
    else:
        print("  selftest subprocess pattern not found (ok)")
    return src

# ─── Apply all patches ────────────────────────────────────────────────────────

patch("launch_ilongrun_supervisor.py", patch_supervisor)
patch("render_ilongrun_install_board.py", patch_install_board)
patch("selftest_ilongrun.py", patch_selftest)

print("\nDone. Now run: curl -fsSL https://raw.githubusercontent.com/acheng-byte/iLongRun/main/install.sh | bash")
