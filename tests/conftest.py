"""Make the shell-harness tests runnable on Windows.

Several tests execute the real update scripts under `bash`:
`test_update_db_protection.py`, `test_update_media_protection.py`,
`test_update_system.py` and `test_power_shutdown.py`. On Windows the `bash` that
PATH resolves to is normally `C:\\Windows\\System32\\bash.exe` — the WSL
launcher — and with no distribution installed it prints "Windows Subsystem for
Linux has no installed distributions" and exits 1. Thirty-odd tests then fail
with an assertion about a scenario, which blames the update scripts for a missing
Linux.

Nothing here needs WSL: Git for Windows ships a bash these tests run green under.
When the `bash` on PATH is unusable, prefer that one. On any other platform, and
when no working bash can be found, PATH is left exactly as it was — a genuinely
missing shell is a real failure and should stay one.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _usable(bash: str) -> bool:
    """True if *bash* actually runs, rather than being a launcher with nothing
    behind it."""
    try:
        done = subprocess.run(
            [bash, "-c", "echo ok"], capture_output=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip().endswith(b"ok")


def _ensure_real_bash() -> None:
    if sys.platform != "win32":
        return

    current = shutil.which("bash")
    if current and _usable(current):
        return

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    for candidate in (
        Path(program_files) / "Git" / "bin" / "bash.exe",
        Path(program_files_x86) / "Git" / "bin" / "bash.exe",
        Path(local_app_data) / "Programs" / "Git" / "bin" / "bash.exe",
    ):
        if candidate.is_file() and _usable(str(candidate)):
            os.environ["PATH"] = (
                str(candidate.parent) + os.pathsep + os.environ.get("PATH", "")
            )
            return


_ensure_real_bash()
