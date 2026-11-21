"""Installation and run-on-startup for modernDash.

Works in place: the program stays in this folder; the installer adds a
``modernDash`` launcher on your PATH that points back here, and can arrange
for the dashboard to start automatically. Everything it creates is removed
again by ``modernDash uninstall``. Standard library only.
"""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
HOME = os.path.expanduser("~")

BLOCK_START = "# >>> modernDash >>>"
BLOCK_END = "# <<< modernDash <<<"
PATH_START = "# >>> modernDash PATH >>>"
PATH_END = "# <<< modernDash PATH <<<"


# -- locations ---------------------------------------------------------------
def venv_dir() -> str:
    return os.path.join(HERE, ".venv")


def venv_python() -> str:
    return os.path.join(venv_dir(), "Scripts" if IS_WIN else "bin", "python.exe" if IS_WIN else "python")


def bin_dir() -> str:
    if IS_WIN:  # under the home folder: %LOCALAPPDATA% is redirected for Microsoft Store Python
        return os.path.join(HOME, ".moderndash", "bin")
    return os.path.join(HOME, ".local", "bin")


def launcher_path() -> str:
    return os.path.join(bin_dir(), "modernDash.cmd" if IS_WIN else "modernDash")


def data_dir() -> str:
    """Where helper scripts for startup live."""
    if IS_WIN:
        return os.path.dirname(bin_dir())
    if IS_MAC:
        return os.path.join(HOME, "Library", "Application Support", "modernDash")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share"), "modernDash")


def windows_startup_file() -> str:
    appdata = os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "modernDash.cmd")


def mac_agent_file() -> str:
    return os.path.join(HOME, "Library", "LaunchAgents", "com.moderndash.startup.plist")


def linux_autostart_file() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
    return os.path.join(base, "autostart", "moderndash.desktop")


def say(message: str = "") -> None:
    print(message)


def ask(question: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes:
        return default
    if not sys.stdin.isatty():
        return default
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer.startswith("y")


# -- environment and launcher ---------------------------------------------------
def ensure_environment(use_venv: bool) -> str:
    """Make sure rich and textual are available; returns the python to launch with."""
    requirements = os.path.join(HERE, "requirements.txt")
    if use_venv:
        if not os.path.isfile(venv_python()):
            say("Creating a private Python environment (.venv) ...")
            import venv
            venv.create(venv_dir(), with_pip=True)
        python = venv_python()
        say("Installing dependencies (rich, textual) ...")
        subprocess.check_call([python, "-m", "pip", "install", "-q", "-r", requirements])
        return python
    missing = []
    for package in ("rich", "textual"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        say(f"Installing {', '.join(missing)} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
    return sys.executable


def write_launcher(python: str) -> str:
    os.makedirs(bin_dir(), exist_ok=True)
    cli = os.path.join(HERE, "cli.py")
    path = launcher_path()
    if IS_WIN:
        body = f'@echo off\r\n"{python}" "{cli}" %*\r\n'
    else:
        body = f'#!/bin/sh\nexec "{python}" "{cli}" "$@"\n'
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    if not IS_WIN:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# -- text blocks inside shell profiles ------------------------------------------
def _strip_block(text: str, start: str, end: str) -> str:
    return re.sub(rf"\n*{re.escape(start)}.*?{re.escape(end)}\n?", "", text, flags=re.S)


def _put_block(path: str, start: str, end: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    text = _strip_block(text, start, end) if start in text else text
    if text and not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{text}\n{start}\n{body.rstrip()}\n{end}\n")


def _drop_block(path: str, start: str, end: str) -> bool:
    if not os.path.isfile(path):
        return False
    text = open(path, encoding="utf-8").read()
    if start not in text:
        return False
    stripped = _strip_block(text, start, end).rstrip("\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(stripped + "\n" if stripped else "")
    return True


def _has_block(path: str, start: str) -> bool:
    return os.path.isfile(path) and start in open(path, encoding="utf-8", errors="replace").read()


def _unix_rc_files(create_for_current: bool) -> list[str]:
    candidates = {
        "bash": [os.path.join(HOME, ".bashrc")],
        "zsh": [os.path.join(HOME, ".zshrc")],
        "fish": [os.path.join(HOME, ".config", "fish", "config.fish")],
    }
    current = os.path.basename(os.environ.get("SHELL", ""))
    files = [p for paths in candidates.values() for p in paths if os.path.isfile(p)]
    if create_for_current and current in candidates:
        for p in candidates[current]:
            if p not in files:
                files.append(p)
    return files


def _powershell_profiles() -> list[str]:
    found: list[str] = []
    for exe in ("powershell", "pwsh"):
        if shutil.which(exe):
            try:
                out = subprocess.run([exe, "-NoProfile", "-Command", "$PROFILE"],
                                     capture_output=True, text=True, timeout=20).stdout.strip()
                if out and out not in found:
                    found.append(out)
            except (OSError, subprocess.SubprocessError):
                pass
    if not found:
        found.append(os.path.join(HOME, "Documents", "WindowsPowerShell", "Microsoft.PowerShell_profile.ps1"))
    return found


def _shell_profiles(create: bool) -> list[str]:
    return _powershell_profiles() if IS_WIN else _unix_rc_files(create)


def _shell_block(path: str, launcher: str) -> str:
    if path.endswith(".ps1"):
        return ('if (-not $env:MODERNDASH_RAN) {\n    $env:MODERNDASH_RAN = "1"\n'
                f'    & "{launcher}" run\n}}')
    if path.endswith(".fish"):
        return ('if status is-interactive; and not set -q MODERNDASH_RAN\n    set -gx MODERNDASH_RAN 1\n'
                f'    "{launcher}" run\nend')
    return ('if [ -t 0 ] && [ -t 1 ] && [ -z "$MODERNDASH_RAN" ]; then\n    export MODERNDASH_RAN=1\n'
            f'    "{launcher}" run\nfi')


# -- PATH ------------------------------------------------------------------------
def _on_path(directory: str) -> bool:
    return os.path.normcase(directory) in [os.path.normcase(p) for p in os.environ.get("PATH", "").split(os.pathsep)]


def _windows_user_path() -> str | None:
    """The user PATH as a brand-new process would see it (None if it can't be read)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('Path','User')"],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _path_contains(path_value: str | None, directory: str) -> bool:
    entries = [os.path.normcase(p.rstrip("\\")) for p in (path_value or "").split(";") if p]
    return os.path.normcase(directory.rstrip("\\")) in entries


def _windows_path_edit(directory: str, add: bool) -> bool:
    """Add/remove ``directory`` on the user PATH. Returns True if the change is visible."""
    import ctypes
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            parts = [p for p in current.split(";") if p]
            parts = [p for p in parts if os.path.normcase(p.rstrip("\\")) != os.path.normcase(directory.rstrip("\\"))]
            if add:
                parts.append(directory)
            winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000, None)
    except OSError:
        pass
    seen = _windows_user_path()
    if seen is None or _path_contains(seen, directory) == add:
        return True
    # The registry write did not take effect (sandboxed Python): let PowerShell do it.
    script = (
        "$d=$env:MD_DIR; $p=[Environment]::GetEnvironmentVariable('Path','User'); "
        "$parts=@(); if($p){$parts=@($p -split ';' | Where-Object { $_ -and $_.TrimEnd('\\') -ine $d.TrimEnd('\\') })}; "
        + ("$parts += $d; " if add else "")
        + "[Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       env={**os.environ, "MD_DIR": directory}, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return _path_contains(_windows_user_path(), directory) == add


def _win_copy(src: str, dst: str) -> None:
    """Copy a file with cmd.exe, which (unlike Store Python) is not sandboxed."""
    subprocess.run(["cmd", "/c", "mkdir", os.path.dirname(dst)], capture_output=True)
    subprocess.run(["cmd", "/c", "copy", "/y", src, dst], check=True, capture_output=True)


def _win_delete(path: str) -> bool:
    exists = subprocess.run(["cmd", "/c", "if", "exist", path, "exit", "0"], capture_output=True).returncode == 0
    subprocess.run(["cmd", "/c", "del", "/f", "/q", path], capture_output=True)
    return exists


def ensure_on_path(assume_yes: bool) -> None:
    directory = bin_dir()
    if IS_WIN:
        if _windows_path_edit(directory, add=True):
            say("Added the command folder to your user PATH.")
        else:
            say(f"Could not update PATH automatically. Add this folder to your PATH yourself:\n  {directory}")
        say("Terminals that were already open will not see it: open a new window, or in this one run:\n"
            f"  $env:Path += ';{directory}'")
        return
    if _on_path(directory):
        return
    line = f'export PATH="{directory}:$PATH"'
    say(f"{directory} is not on your PATH.")
    if ask("Add it to your shell profile?", True, assume_yes):
        for rc in _unix_rc_files(create_for_current=True) or [os.path.join(HOME, ".profile")]:
            body = 'set -gx PATH "%s" $PATH' % directory if rc.endswith(".fish") else line
            _put_block(rc, PATH_START, PATH_END, body)
        say("Done. Open a new terminal to use `modernDash`.")
    else:
        say(f"Add this to your shell profile yourself:\n  {line}")


def remove_from_path() -> None:
    if IS_WIN:
        if not _windows_path_edit(bin_dir(), add=False):
            say("Could not remove the PATH entry automatically; remove it in Environment Variables.")
        return
    for rc in _unix_rc_files(False) + [os.path.join(HOME, ".profile")]:
        _drop_block(rc, PATH_START, PATH_END)


# -- startup ---------------------------------------------------------------------
def _linux_startup_script(launcher: str) -> str:
    return f"""#!/bin/sh
L="{launcher}"
have() {{ command -v "$1" >/dev/null 2>&1; }}
if have x-terminal-emulator; then exec x-terminal-emulator -e "$L" run
elif have gnome-terminal; then exec gnome-terminal -- "$L" run
elif have konsole; then exec konsole -e "$L" run
elif have xfce4-terminal; then exec xfce4-terminal -x "$L" run
elif have kitty; then exec kitty "$L" run
elif have alacritty; then exec alacritty -e "$L" run
elif have foot; then exec foot "$L" run
elif have xterm; then exec xterm -e "$L" run
fi
"""


def startup_enable(mode: str) -> None:
    launcher = launcher_path()
    if not os.path.isfile(launcher):
        raise SystemExit("The modernDash command is not installed yet. Run `python install.py` first.")
    if mode == "shell":
        for path in _shell_profiles(create=True):
            _put_block(path, BLOCK_START, BLOCK_END, _shell_block(path, launcher))
            say(f"Added a startup block to {path}")
        say("modernDash will now run in every new terminal. Press any key to dismiss it.")
        return
    if mode != "login":
        raise SystemExit("Mode must be 'login' or 'shell'.")
    if IS_WIN:
        path = windows_startup_file()
        os.makedirs(data_dir(), exist_ok=True)
        staged = os.path.join(data_dir(), "startup.cmd")
        with open(staged, "w", encoding="utf-8", newline="") as f:
            f.write(f'@echo off\r\nstart "modernDash" cmd /k ""{launcher}" run"\r\n')
        _win_copy(staged, path)
    elif IS_MAC:
        os.makedirs(data_dir(), exist_ok=True)
        command = os.path.join(data_dir(), "startup.command")
        with open(command, "w", encoding="utf-8") as f:
            f.write(f'#!/bin/sh\n"{launcher}" run\n')
        os.chmod(command, 0o755)
        path = mac_agent_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump({"Label": "com.moderndash.startup", "RunAtLoad": True,
                           "ProgramArguments": ["/usr/bin/open", "-a", "Terminal", command]}, f)
    else:
        os.makedirs(data_dir(), exist_ok=True)
        script = os.path.join(data_dir(), "startup.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(_linux_startup_script(launcher))
        os.chmod(script, 0o755)
        path = linux_autostart_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=modernDash\n"
                    f'Exec="{script}"\nTerminal=false\nX-GNOME-Autostart-enabled=true\n')
    say(f"Created {path}\nmodernDash will open in a terminal window the next time you log in.")


def startup_disable() -> list[str]:
    removed: list[str] = []
    if IS_WIN and _win_delete(windows_startup_file()):
        removed.append(windows_startup_file())
    for path in (windows_startup_file(), mac_agent_file(), linux_autostart_file(),
                 os.path.join(data_dir(), "startup.sh"), os.path.join(data_dir(), "startup.command"),
                 os.path.join(data_dir(), "startup.cmd")):
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)
    for path in _shell_profiles(create=False):
        if _drop_block(path, BLOCK_START, BLOCK_END):
            removed.append(path)
    return removed


def startup_status() -> None:
    login = windows_startup_file() if IS_WIN else mac_agent_file() if IS_MAC else linux_autostart_file()
    say(f"command installed : {'yes' if os.path.isfile(launcher_path()) else 'no'} ({launcher_path()})")
    on_path = _path_contains(_windows_user_path(), bin_dir()) if IS_WIN else _on_path(bin_dir())
    say(f"on PATH           : {'yes' if on_path else 'no'}")
    say(f"run at login      : {'on' if os.path.isfile(login) else 'off'}")
    shells = [p for p in _shell_profiles(create=False) if _has_block(p, BLOCK_START)]
    say(f"run in new terminal: {'on (' + ', '.join(shells) + ')' if shells else 'off'}")


# -- commands ---------------------------------------------------------------------
def _flag(args: list[str], name: str) -> bool:
    return name in args


def run(command: str, args: list[str]) -> int:
    if command == "install":
        assume_yes = _flag(args, "--yes") or _flag(args, "-y")
        python = ensure_environment(use_venv=not _flag(args, "--no-venv"))
        launcher = write_launcher(python)
        say(f"Installed command: {launcher}")
        ensure_on_path(assume_yes)
        mode = next((a.split("=", 1)[1] for a in args if a.startswith("--startup=")), None)
        if _flag(args, "--startup"):
            mode = "login"
        if _flag(args, "--no-startup"):
            mode = "none"
        if mode is None and ask("Start modernDash automatically?", False, assume_yes):
            mode = "login" if ask("Open a window at login (otherwise: run in every new terminal)?", True, assume_yes) else "shell"
        if mode in ("login", "shell"):
            startup_enable(mode)
        say("\nAll set. Open a new terminal and try:\n  modernDash run\n  modernDash layout\n  modernDash config --help")
        return 0

    if command == "uninstall":
        removed = startup_disable()
        if os.path.isfile(launcher_path()):
            os.remove(launcher_path())
            removed.append(launcher_path())
        remove_from_path()
        if _flag(args, "--purge") and os.path.isdir(venv_dir()):
            shutil.rmtree(venv_dir())
            removed.append(venv_dir())
        say("Removed:\n  " + "\n  ".join(removed) if removed else "Nothing to remove.")
        say("The program folder and your startup.json were left in place.")
        return 0

    # startup
    action = args[0].lower() if args else "status"
    if action == "enable":
        startup_enable(args[1].lower() if len(args) > 1 else "login")
    elif action == "disable":
        removed = startup_disable()
        say("Startup disabled." if removed else "Startup was not enabled.")
    elif action == "status":
        startup_status()
    else:
        say("Usage: modernDash startup enable [login|shell] | disable | status")
        return 2
    return 0
