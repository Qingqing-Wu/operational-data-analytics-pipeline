import subprocess
from pathlib import Path
from datetime import datetime
import os
import sys


os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"


PROJECT_ROOT = Path(r"C:\Users")


SCRIPTS_DIR = PROJECT_ROOT / "SQL pipeline" / "automation script"

# log dictionary
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents = True, exist_ok = True)

# 7 scripts
SCRIPTS = [
    "outbound to sql.py",
    "inbound to sql.py",
    "transfer to sql.py",
    "outbound value-add to sql.py",
    "outbound custom-record to sql.py",
    "prebuilt custom-record to sql.py",
    "prebuilt value-add to sql.py",
]

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"etl_run_{ts}.log"

    python_exe = sys.executable

    header = (
        f"Time: {ts}\n"
        f"Python: {python_exe}\n"
        f"Project: {PROJECT_ROOT}\n"
        f"Scripts Dir: {SCRIPTS_DIR}\n\n"
    )
    log_file.write_text(header, encoding="utf-8")

    for script_name in SCRIPTS:
        script_path = SCRIPTS_DIR / script_name
        banner = f"\n=== Running: {script_path} ===\n"
        print(banner, end="")
        log_file.write_text(log_file.read_text(encoding="utf-8") + banner, encoding="utf-8")

        if not script_path.exists():
            msg = f"[MISSING FILE] {script_path}\n"
            print(msg, end="")
            log_file.write_text(log_file.read_text(encoding="utf-8") + msg, encoding="utf-8")
            continue

        result = subprocess.run(
            [python_exe, "-X", "utf8", str(script_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        output = (result.stdout or "") + (result.stderr or "")
        if output:
            print(output, end="")
            log_file.write_text(log_file.read_text(encoding="utf-8") + output, encoding="utf-8")

    print("\nALL DONE")

if __name__ == "__main__":
    main()

