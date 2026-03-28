"""Django views for Activity Timer plugin."""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from .models import TimerPreset, TimerConfig, TimerSession
from .forms import TimerConfigForm, QuickTimerForm, TimerControlForm
from .timer_service import timer_service

logger = logging.getLogger(__name__)


class TimerDashboardView(View):
    """Main dashboard view for the Activity Timer."""

    def get(self, request):
        """Display the timer dashboard."""
        # Get all active timer configurations
        configs = TimerConfig.objects.filter(is_active=True).order_by("name")

        # Get all active presets
        presets = TimerPreset.objects.filter(is_active=True).order_by("preset_type")

        # Get the default config
        default_config = TimerConfig.objects.filter(
            is_default=True, is_active=True
        ).first()

        # Get recent timer sessions (last 10)
        recent_sessions = TimerSession.objects.all()[:10]

        # Get currently active session
        active_session = timer_service.get_active_session()

        context = {
            "title": _("Activity Timer"),
            "configs": configs,
            "presets": presets,
            "default_config": default_config,
            "recent_sessions": recent_sessions,
            "active_session": active_session,
            "quick_form": QuickTimerForm(),
            "is_running": timer_service.is_timer_running(),
        }

        return render(request, "activity_timer/dashboard.html", context)


class TimerControlView(View):
    """API view for timer control actions."""

    @method_decorator(require_POST)
    def post(self, request):
        """Handle timer control actions."""
        action = request.POST.get("action")
        config_id = request.POST.get("config_id")
        preset_id = request.POST.get("preset_id")

        logger.info(
            f"Timer action received: {action}, config_id: {config_id}, preset_id: {preset_id}"
        )

        try:
            if action == "start":
                return self._start_timer(config_id, request, preset_id)
            elif action == "pause":
                return self._pause_timer()
            elif action == "resume":
                return self._resume_timer()
            elif action == "stop":
                return self._stop_timer()
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Invalid action"),
                    },
                    status=400,
                )

        except Exception as e:
            logger.error(f"Error handling timer action {action}: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )

    def _start_timer(self, config_id, request, preset_id=None):
        """Start a new timer session."""
        config = None

        # If preset_id is provided, create a config from preset
        if preset_id:
            preset = get_object_or_404(TimerPreset, id=preset_id, is_active=True)
            config = TimerConfig.objects.create(
                name=preset.name,
                description=preset.description,
                duration_minutes=preset.duration_minutes,
                display_color=preset.display_color,
                led_color_start=preset.led_color_start,
                led_color_warning=preset.led_color_warning,
                led_color_end=preset.led_color_end,
                enable_breathing=preset.enable_breathing,
                enable_ambient_sound=preset.enable_ambient_sound,
                is_active=True,
            )
        elif config_id:
            config = get_object_or_404(TimerConfig, id=config_id, is_active=True)
        else:
            # Use default config or first active config
            config = TimerConfig.objects.filter(is_default=True, is_active=True).first()
            if not config:
                config = TimerConfig.objects.filter(is_active=True).first()

            if not config:
                # Create a default config
                config = TimerConfig.objects.create(
                    name=_("Default Timer"),
                    duration_minutes=10,
                    is_default=True,
                    is_active=True,
                )

        # Check if timer is already running
        if timer_service.is_timer_running():
            timer_service.stop_timer()

        # Create new session
        duration_seconds = config.get_duration_seconds()
        session = TimerSession.objects.create(
            config=config,
            duration_seconds=duration_seconds,
            remaining_seconds=duration_seconds,
        )

        # Initialize GPIO and start timer
        timer_service.initialize_gpio(
            red_pin=17,
            green_pin=27,
            blue_pin=22,
            buzzer_pin=24,
            brightness=100,
        )

        timer_service.start_timer(session)

        return JsonResponse(
            {
                "success": True,
                "session_id": session.id,
                "duration_seconds": duration_seconds,
                "remaining_seconds": session.remaining_seconds,
                "message": _("Timer started"),
            }
        )

    def _pause_timer(self):
        """Pause the current timer."""
        timer_service.pause_timer()
        return JsonResponse(
            {
                "success": True,
                "message": _("Timer paused"),
            }
        )

    def _resume_timer(self):
        """Resume the paused timer."""
        timer_service.resume_timer()
        return JsonResponse(
            {
                "success": True,
                "message": _("Timer resumed"),
            }
        )

    def _stop_timer(self):
        """Stop the current timer."""
        timer_service.stop_timer()
        return JsonResponse(
            {
                "success": True,
                "message": _("Timer stopped"),
            }
        )


class TimerStatusView(View):
    """API view for getting current timer status."""

    def get(self, request):
        """Get current timer status."""
        session = timer_service.get_active_session()

        if session:
            return JsonResponse(
                {
                    "success": True,
                    "has_active_session": True,
                    "session": {
                        "id": session.id,
                        "status": session.status,
                        "status_display": session.get_status_display(),
                        "duration_seconds": session.duration_seconds,
                        "remaining_seconds": session.remaining_seconds,
                        "progress_percent": session.get_progress_percent(),
                        "remaining_display": session.get_remaining_display(),
                        "current_color": session.get_current_color(),
                    },
                }
            )
        else:
            return JsonResponse(
                {
                    "success": True,
                    "has_active_session": False,
                }
            )


class TimerConfigListView(View):
    """View for listing and managing timer configurations."""

    def get(self, request):
        """Display list of timer configurations."""
        configs = TimerConfig.objects.all().order_by("-is_active", "name")

        context = {
            "title": _("Timer Configurations"),
            "configs": configs,
        }

        return render(request, "activity_timer/config_list.html", context)


class TimerConfigCreateView(View):
    """View for creating new timer configurations."""

    def get(self, request):
        """Display the configuration form."""
        form = TimerConfigForm()

        context = {
            "title": _("Create Timer Configuration"),
            "form": form,
            "action": _("Create"),
        }

        return render(request, "activity_timer/config_form.html", context)

    def post(self, request):
        """Handle form submission."""
        form = TimerConfigForm(request.POST)

        if form.is_valid():
            form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Configuration created successfully"),
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                },
                status=400,
            )


class TimerConfigUpdateView(View):
    """View for updating timer configurations."""

    def get(self, request, config_id):
        """Display the configuration form with existing data."""
        config = get_object_or_404(TimerConfig, id=config_id)
        form = TimerConfigForm(instance=config)

        context = {
            "title": _("Edit Timer Configuration"),
            "form": form,
            "config": config,
            "action": _("Update"),
        }

        return render(request, "activity_timer/config_form.html", context)

    def post(self, request, config_id):
        """Handle form submission."""
        config = get_object_or_404(TimerConfig, id=config_id)
        form = TimerConfigForm(request.POST, instance=config)

        if form.is_valid():
            form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Configuration updated successfully"),
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                },
                status=400,
            )


class TimerConfigDeleteView(View):
    """View for deleting timer configurations."""

    @method_decorator(require_POST)
    def post(self, request, config_id):
        """Delete a timer configuration."""
        config = get_object_or_404(TimerConfig, id=config_id)
        config.delete()

        return JsonResponse(
            {
                "success": True,
                "message": _("Configuration deleted successfully"),
            }
        )
