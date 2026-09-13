import os
import json
import subprocess
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from pathlib import Path
from .models import UpdateStatus

# Configuration
STATUS_FILE = Path("/run/tinko-update/status.json")
TRIGGER_FILE = Path("/run/tinko-update/trigger")

def write_trigger_file(update_id):
    """Writes the trigger file to start the daemon."""
    TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRIGGER_FILE, 'w') as f:
        json.dump({"update_id": str(update_id), "created_at": datetime.utcnow().isoformat() + "Z"}, f)

def reconcile_update_records():
    """Sync UpdateStatus DB rows with the daemon's status file.

    The daemon (a stdlib-only process) writes the final result to status.json
    but cannot touch the DB, so we reconcile here on the next request:
    - a terminal status.json (completed/failed) with an update_id syncs its row;
    - in-progress rows older than 24h are marked failed (abandoned after a
      daemon crash). Running updates are never touched.
    """
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
            update_id = data.get("update_id")
            final_status = data.get("status")
            if update_id is not None and final_status in ("completed", "failed"):
                updates = {
                    "status": final_status,
                    "completed_at": timezone.now(),
                }
                if final_status == "failed":
                    updates["error_message"] = data.get("error")
                UpdateStatus.objects.filter(id=update_id, status="in_progress").update(**updates)
    except (json.JSONDecodeError, IOError):
        pass

    UpdateStatus.objects.filter(
        status="in_progress",
        started_at__lt=timezone.now() - timedelta(hours=24),
    ).update(
        status="failed",
        completed_at=timezone.now(),
        error_message="Update abandoned (stale record)",
    )

def check_for_updates():
    """Runs git commands to see if the repo is ahead of origin/master."""
    repo_path = Path("/home/tinko/edu-pi")
    try:
        # Fetch latest (with timeout to avoid hanging on network issues)
        subprocess.run(["git", "fetch"], cwd=repo_path, check=True, capture_output=True, timeout=30)

        # Get commit diff
        result = subprocess.run(
            ["git", "log", "HEAD..origin/master", "--oneline"],
            cwd=repo_path, check=True, capture_output=True, text=True, timeout=10
        )
        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []

        return {
            "available": len(commits) > 0,
            "commits": commits,
            "current_version": subprocess.run(
                ["git", "describe", "--tags"],
                cwd=repo_path, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        }
    except subprocess.TimeoutExpired:
        return {"error": "Git fetch timed out — check internet connection"}
    except Exception as e:
        return {"error": str(e)}

def check_updates(request):
    """Check for available updates."""
    result = check_for_updates()
    if "error" in result:
        return JsonResponse({"error": result["error"]}, status=500)
    return JsonResponse(result)

def start_update(request):
    """Trigger the system update process."""
    # 0. Reconcile DB records with the daemon's last result first, so a
    # previous run (even one that died) never blocks future updates.
    reconcile_update_records()

    # 1. Rate limit check (5 minutes)
    last_update = UpdateStatus.objects.filter(
        status__in=['completed', 'in_progress']
    ).order_by('-started_at').first()

    if last_update and last_update.started_at > timezone.now() - timedelta(minutes=5):
        return JsonResponse({
            'error': 'Updates can only be run every 5 minutes',
            'next_update_at': (last_update.started_at + timedelta(minutes=5)).isoformat()
        }, status=429)

    # 2. In-progress check
    if UpdateStatus.objects.filter(status='in_progress').exists():
        return JsonResponse({'error': 'Update already in progress'}, status=409)

    # 3. Create record
    update = UpdateStatus.objects.create(
        user=request.user if request.user.is_authenticated else None,
        status='in_progress',
    )

    # 4. Trigger daemon
    try:
        write_trigger_file(update.id)
    except Exception as e:
        return JsonResponse({'error': f'Failed to trigger update daemon: {str(e)}'}, status=500)

    return JsonResponse({'update_id': update.id})

def get_update_status(request):
    """Poll the current status from the status file."""
    reconcile_update_records()

    if not STATUS_FILE.exists():
        return JsonResponse({'status': 'idle', 'stage': None})

    try:
        with open(STATUS_FILE, 'r') as f:
            return JsonResponse(json.load(f))
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_last_update_info(request):
    """Return the date of the last commit on the installed code and the last
    successful web update. Cheap: reads only local git HEAD and one DB row
    (no network, no git fetch)."""
    info = {"git_last_commit": None, "last_successful_update": None}
    repo_path = Path("/home/tinko/edu-pi")
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, timeout=10, cwd=repo_path
        )
        if r.returncode == 0 and r.stdout.strip():
            info["git_last_commit"] = r.stdout.strip()
    except Exception:
        pass

    last_ok = UpdateStatus.objects.filter(status="completed").order_by("-completed_at").first()
    if last_ok and last_ok.completed_at:
        info["last_successful_update"] = last_ok.completed_at.isoformat()
    return JsonResponse(info)
