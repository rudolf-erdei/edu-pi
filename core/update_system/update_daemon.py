import os
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Configuration
PROJECT_ROOT = "/home/tinko/edu-pi"
TRIGGER_FILE = Path("/run/tinko-update/trigger")
STATUS_FILE = Path("/run/tinko-update/status.json")
UPDATE_SCRIPT = Path(PROJECT_ROOT) / "update-web.sh"

def ensure_directories():
    """Ensure the /run/tinko-update directory exists."""
    TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)

def write_status(data):
    """Atomically write status JSON."""
    temp_file = STATUS_FILE.with_suffix(".json.tmp")
    with open(temp_file, 'w') as f:
        json.dump(data, f, indent=2)
    temp_file.replace(STATUS_FILE)

def get_current_status():
    """Read current status file or return default."""
    if not STATUS_FILE.exists():
        return {
            "status": "idle",
            "stage": None,
            "stages_completed": [],
            "logs": [],
            "error": None,
            "started_at": None,
            "completed_at": None
        }
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def log_to_status(status_data, message):
    """Append a log message to the status object."""
    status_data["logs"].append({
        "time": datetime.utcnow().isoformat() + "Z",
        "message": message
    })
    # Keep logs size manageable
    if len(status_data["logs"]) > 1000:
        status_data["logs"] = status_data["logs"][-1000:]
    write_status(status_data)

def run_update(update_id):
    """Execute the update script and manage the status file."""
    print(f"Starting update {update_id}...")

    status = {
        "update_id": update_id,
        "status": "in_progress",
        "stage": "initialization",
        "stages_completed": [],
        "logs": [],
        "error": None,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "completed_at": None
    }
    write_status(status)

    env = os.environ.copy()
    env["TINKO_UPDATE_DAEMON"] = "1"
    env["INSTALL_DIR"] = PROJECT_ROOT

    try:
        # Run the script and stream output
        process = subprocess.Popen(
            ["/bin/bash", str(UPDATE_SCRIPT)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        while True:
            line = process.stdout.readline()
            if not line:
                break

            log_line = line.strip()
            if log_line:
                log_to_status(status, log_line)

            # Sync stage from the status file written by update-web.sh
            # update-web.sh writes its own status.json, we merge it here
            current_script_status = get_current_status()
            if current_script_status.get("stage") != status["stage"]:
                status["stage"] = current_script_status.get("stage")
                if current_script_status.get("status") == "completed":
                    status["stages_completed"].append(status["stage"])
                write_status(status)

        return_code = process.wait()

        if return_code == 0:
            status["status"] = "completed"
            status["stage"] = "finished"
            status["completed_at"] = datetime.utcnow().isoformat() + "Z"
            log_to_status(status, "Update completed successfully.")
        else:
            status["status"] = "failed"
            status["error"] = f"Update script failed with exit code {return_code}"
            log_to_status(status, f"Update failed with exit code {return_code}")

    except Exception as e:
        status["status"] = "failed"
        status["error"] = str(e)
        log_to_status(status, f"Daemon error: {str(e)}")

    write_status(status)

def recover_interrupted_update():
    """Check for leftover triggers and recover state."""
    if TRIGGER_FILE.exists():
        print("Found leftover trigger file. Recovering...")
        try:
            with open(TRIGGER_FILE, 'r') as f:
                trigger_data = json.load(f)
                update_id = trigger_data.get("update_id")

            status = get_current_status()
            if status.get("status") == "in_progress":
                print(f"Resuming interrupted update {update_id}...")
                run_update(update_id)
            else:
                print("Cleaning up stale trigger file.")
                TRIGGER_FILE.unlink()
        except Exception as e:
            print(f"Recovery failed: {e}")

def main():
    ensure_directories()
    recover_interrupted_update()

    print("Tinko Update Daemon started. Monitoring for triggers...")

    while True:
        if TRIGGER_FILE.exists():
            try:
                with open(TRIGGER_FILE, 'r') as f:
                    trigger_data = json.load(f)
                    update_id = trigger_data.get("update_id")

                run_update(update_id)

                # Clean up trigger
                TRIGGER_FILE.unlink()

            except Exception as e:
                print(f"Error processing trigger: {e}")
                # Avoid infinite loop on corrupted trigger file
                if TRIGGER_FILE.exists():
                    TRIGGER_FILE.unlink()

        time.sleep(1)

if __name__ == "__main__":
    main()
