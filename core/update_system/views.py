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

def check_for_updates():
    """Runs git commands to see if the repo is ahead of origin/main."""
    repo_path = Path("/home/tinko/edu-pi")
    try:
        # Fetch latest
        subprocess.run(["git", "fetch"], cwd=repo_path, check=True, capture_output=True)

        # Get commit diff
        result = subprocess.run(
            ["git", "log", "HEAD..origin/main", "--oneline"],
            cwd=repo_path, check=True, capture_output=True, text=True
        )
        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []

        return {
            "available": len(commits) > 0,
            "commits": commits,
            "current_version": subprocess.run(
                ["git", "describe", "--tags"],
                cwd=repo_path, capture_output=True, text=True
            ).stdout.strip()
        }
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
    if not STATUS_FILE.exists():
        return JsonResponse({'status': 'idle', 'stage': None})

    try:
        with open(STATUS_FILE, 'r') as f:
            return JsonResponse(json.load(f))
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
