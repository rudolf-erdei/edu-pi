"""Views for Noise Monitor plugin."""

import json
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, FormView

from datetime import timedelta

from .forms import ProfileSelectForm, CustomThresholdForm, NoiseMonitorControlForm
from .models import NoiseProfile, NoiseMonitorConfig, NoiseReading
from .noise_service import noise_service
from .startup import start_monitoring as start_configured_monitoring

logger = logging.getLogger(__name__)


class NoiseMonitorDashboardView(TemplateView):
    """Dashboard view for noise monitor."""

    template_name = "noise_monitor/dashboard.html"

    def get_context_data(self, **kwargs):
        """Add noise data to context."""
        context = super().get_context_data(**kwargs)

        # Get or create default config
        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        if not config:
            # Seeded in the active language, so a teacher whose interface is
            # Romanian does not get an English profile name on a page that is
            # otherwise translated. The name is stored data once written and
            # does not follow a later language change.
            # Not `_`: that name is gettext in this module, and binding it as
            # the throwaway makes every gettext call above it raise
            # UnboundLocalError.
            profile, _created = NoiseProfile.objects.get_or_create(
                profile_type=NoiseProfile.ProfileType.TEACHING,
                defaults={
                    "name": _("Teaching"),
                    "description": _("Moderate noise levels for normal teaching"),
                    "yellow_threshold": 40,
                    "red_threshold": 70,
                },
            )
            config = NoiseMonitorConfig.objects.create(
                name=_("Default"),
                profile=profile,
                is_default=True,
            )

        context["config"] = config
        context["profile"] = config.profile
        context["is_monitoring"] = noise_service._is_monitoring

        # Get current levels
        levels = noise_service.get_current_levels()
        context["instant_average"] = levels["instant_average"]
        context["session_average"] = levels["session_average"]
        context["instant_color"] = levels["instant_color"]
        context["session_color"] = levels["session_color"]

        # Whether those levels came from a microphone or from the simulated
        # fallback, so the page can say so before the first WebSocket message.
        context["microphone_available"] = levels["microphone_available"]
        context["device_status"] = levels["device_status"]
        context["device_name"] = levels["device_name"]

        # Recent readings (last 50)
        context["recent_readings"] = NoiseReading.objects.filter(
            config=config
        ).order_by("-timestamp")[:50]

        return context


def custom_config_initial() -> dict:
    """
    Build the initial values for the custom threshold form from stored state.

    Returns:
        dict: Field names to values, empty when nothing is configured yet.
    """
    config = NoiseMonitorConfig.objects.filter(is_active=True).first()
    if not config:
        return {}

    initial = {
        "name": config.name,
        "instant_window_seconds": config.instant_window_seconds,
        "session_window_minutes": config.session_window_minutes,
        "led_brightness": config.led_brightness,
    }

    if config.profile:
        initial["yellow_threshold"] = config.profile.yellow_threshold
        initial["red_threshold"] = config.profile.red_threshold

    return initial


class NoiseMonitorConfigView(FormView):
    """View for configuring noise monitor."""

    template_name = "noise_monitor/config_form.html"
    form_class = ProfileSelectForm
    success_url = reverse_lazy("noise_monitor:dashboard")

    def get_initial(self):
        """Show what is saved, so a submit here cannot quietly replace it.

        Every field this form writes is seeded from the stored configuration.
        Left at the field defaults the form showed 10/5/100 and the first
        profile regardless of what was configured, so applying the profile
        without changing anything reset the windows, the brightness and the
        profile — the same defect the custom form had.

        The microphone picker fills its own select from the API, but the form
        must already carry the saved device: without it, a page load before the
        request finishes (or with JavaScript unavailable) posts an empty device
        and switches the monitor back to automatic.
        """
        initial = super().get_initial()

        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        if config:
            initial["instant_window_seconds"] = config.instant_window_seconds
            initial["session_window_minutes"] = config.session_window_minutes
            initial["led_brightness"] = config.led_brightness
            # Left at the field default, the checkbox would come up ticked on a
            # configuration that has auto-start switched off, and the next
            # submit would switch it back on.
            initial["auto_start"] = config.auto_start
            initial["audio_input_device"] = config.audio_input_device
            initial["audio_input_device_index"] = config.audio_input_device_index
            if config.profile_id:
                initial["profile"] = config.profile_id

        return initial

    def get_context_data(self, **kwargs):
        """Add custom threshold form to context."""
        context = super().get_context_data(**kwargs)
        # Pre-filled with what is actually configured. Left at the field
        # defaults, this form rendered "Custom Configuration" and thresholds of
        # 40/70 no matter what was saved — so a teacher who opened the page and
        # pressed the button without touching anything had their saved name and
        # thresholds silently overwritten.
        context["custom_form"] = CustomThresholdForm(initial=custom_config_initial())
        context["profiles"] = NoiseProfile.objects.filter(is_active=True)
        # The profile cards mark the one in use, which needs the stored
        # configuration to compare against. Without it `config` resolves to
        # nothing in the template and the badge never appears.
        context["config"] = NoiseMonitorConfig.objects.filter(is_active=True).first()
        return context

    def form_valid(self, form):
        """Handle profile selection."""
        profile = form.cleaned_data["profile"]

        config, created = NoiseMonitorConfig.objects.get_or_create(
            is_default=True,
            defaults={
                "name": f"Profile: {profile.name}",
                "profile": profile,
            },
        )

        if not created:
            config.profile = profile
            config.name = f"Profile: {profile.name}"

        # Update settings
        config.auto_start = form.cleaned_data.get("auto_start", False)
        config.instant_window_seconds = form.cleaned_data["instant_window_seconds"]
        config.session_window_minutes = form.cleaned_data["session_window_minutes"]
        config.led_brightness = form.cleaned_data["led_brightness"]
        config.audio_input_device = form.cleaned_data.get("audio_input_device", "")
        config.audio_input_device_index = form.cleaned_data.get("audio_input_device_index")
        config.save()

        # Update service configuration
        noise_service.configure(
            yellow_threshold=profile.yellow_threshold,
            red_threshold=profile.red_threshold,
            instant_window_seconds=config.instant_window_seconds,
            session_window_minutes=config.session_window_minutes,
            brightness=config.led_brightness,
        )

        # An empty selection means automatic, so this is called either way.
        noise_service.set_device(
            config.audio_input_device_index, config.audio_input_device
        )

        logger.info(f"Noise monitor configured with profile: {profile.name}")
        return super().form_valid(form)


class CustomThresholdConfigView(FormView):
    """View for custom threshold configuration."""

    template_name = "noise_monitor/custom_config.html"
    form_class = CustomThresholdForm
    success_url = reverse_lazy("noise_monitor:dashboard")

    def get_initial(self):
        """Show what is configured, for the same reason as the config page."""
        initial = super().get_initial()
        initial.update(custom_config_initial())
        return initial

    def form_valid(self, form):
        """Handle custom threshold form submission."""
        # Get or create custom profile
        custom_profile, _ = NoiseProfile.objects.get_or_create(
            profile_type=NoiseProfile.ProfileType.CUSTOM,
            defaults={
                "name": "Custom",
                "description": "User-defined custom thresholds",
                "yellow_threshold": form.cleaned_data["yellow_threshold"],
                "red_threshold": form.cleaned_data["red_threshold"],
            },
        )

        # Update thresholds
        custom_profile.yellow_threshold = form.cleaned_data["yellow_threshold"]
        custom_profile.red_threshold = form.cleaned_data["red_threshold"]
        custom_profile.save()

        # Create/update config
        config, _ = NoiseMonitorConfig.objects.get_or_create(
            is_default=True,
            defaults={
                "name": form.cleaned_data["name"],
                "profile": custom_profile,
                "instant_window_seconds": form.cleaned_data["instant_window_seconds"],
                "session_window_minutes": form.cleaned_data["session_window_minutes"],
                "led_brightness": form.cleaned_data["led_brightness"],
            },
        )

        config.name = form.cleaned_data["name"]
        config.profile = custom_profile
        config.instant_window_seconds = form.cleaned_data["instant_window_seconds"]
        config.session_window_minutes = form.cleaned_data["session_window_minutes"]
        config.led_brightness = form.cleaned_data["led_brightness"]
        # The microphone selection is left alone: this form has no microphone
        # field, and the device belongs to the profile form.
        config.save()

        # Update service
        noise_service.configure(
            yellow_threshold=custom_profile.yellow_threshold,
            red_threshold=custom_profile.red_threshold,
            instant_window_seconds=config.instant_window_seconds,
            session_window_minutes=config.session_window_minutes,
            brightness=config.led_brightness,
        )

        logger.info(
            f"Custom thresholds set: yellow={custom_profile.yellow_threshold}, red={custom_profile.red_threshold}"
        )
        return super().form_valid(form)


class NoiseProfileRenameView(View):
    """Rename a noise profile and edit its description.

    ``NoiseProfile.profile_type`` is unique, so there is exactly one profile
    per type and the seeded name ("Teaching") is what the teacher is stuck
    with until this exists.
    """

    def post(self, request, pk, *args, **kwargs):
        """Apply the new name and description."""
        profile = get_object_or_404(NoiseProfile, pk=pk)
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        error = None
        if not name:
            error = _("The profile name cannot be empty.")
        elif len(name) > 100:
            error = _("The profile name cannot be longer than 100 characters.")
        elif (
            NoiseProfile.objects.filter(name__iexact=name)
            .exclude(pk=profile.pk)
            .exists()
        ):
            # Two profiles with the same name are indistinguishable in the
            # dropdown on the same page.
            error = _("Another profile already uses that name.")

        if error:
            messages.error(request, error)
        else:
            profile.name = name
            profile.description = description
            profile.save()
            messages.success(
                request, _("Profile saved as “%(name)s”.") % {"name": name}
            )

        return redirect("noise_monitor:config")


class NoiseProfileDeleteView(View):
    """Delete a noise profile."""

    def post(self, request, pk, *args, **kwargs):
        """Delete the profile, unless it is the last one."""
        profile = get_object_or_404(NoiseProfile, pk=pk)
        name = profile.name

        # Deleting the last one would leave the profile dropdown on the
        # configuration page empty, and the form there cannot be submitted
        # without a profile — the page would be stuck.
        if NoiseProfile.objects.count() <= 1:
            messages.error(
                request,
                _(
                    "This is the only profile left. Create another one before "
                    "deleting it."
                ),
            )
            return redirect("noise_monitor:config")

        # Any configuration pointing at it is left without a profile
        # (on_delete=SET_NULL) and falls back to the default thresholds until
        # another one is chosen.
        profile.delete()
        messages.success(request, _("Profile “%(name)s” deleted.") % {"name": name})

        return redirect("noise_monitor:config")


class NoiseMonitorControlView(View):
    """View for controlling noise monitoring (start/stop)."""

    def post(self, request, *args, **kwargs):
        """Handle control actions."""
        action = request.POST.get("action")

        if action == "start":
            self._start_monitoring()
        elif action == "stop":
            self._stop_monitoring()
        elif action == "reset":
            self._reset_session()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"status": "ok", "is_monitoring": noise_service.is_monitoring()}
            )

        return redirect("noise_monitor:dashboard")

    def _start_monitoring(self):
        """Start noise monitoring."""
        # Same call the plugin makes at boot, so a teacher pressing Start gets
        # exactly what the Pi would have started on its own.
        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        start_configured_monitoring(config)
        logger.info("Noise monitoring started")

    def _stop_monitoring(self):
        """Stop noise monitoring."""
        noise_service.stop_monitoring()
        logger.info("Noise monitoring stopped")

    def _reset_session(self):
        """Reset session data."""
        noise_service.stop_monitoring()
        # Clear old readings (optional - keep recent history)
        cutoff = timezone.now() - timedelta(hours=1)
        NoiseReading.objects.filter(timestamp__lt=cutoff).delete()

        # Restart if it was running
        if self.request.POST.get("was_monitoring") == "true":
            self._start_monitoring()

        logger.info("Session reset")


class NoiseLevelAPIView(View):
    """API endpoint for current noise levels."""

    def get(self, request, *args, **kwargs):
        """Return current noise levels."""
        levels = noise_service.get_current_levels()
        return JsonResponse(levels)


class NoiseHistoryAPIView(View):
    """API endpoint for noise history."""

    def get(self, request, *args, **kwargs):
        """Return recent noise readings."""
        limit = int(request.GET.get("limit", 50))

        readings = NoiseReading.objects.all().order_by("-timestamp")[:limit]

        data = {
            "readings": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "instant_average": r.instant_average,
                    "session_average": r.session_average,
                    "instant_color": r.instant_color,
                    "session_color": r.session_color,
                }
                for r in readings
            ]
        }

        return JsonResponse(data)


class AudioDevicesAPIView(View):
    """API endpoint to list available audio input devices."""

    def get(self, request, *args, **kwargs):
        """Return list of available audio input devices."""
        from .noise_service import MICROPHONE_AVAILABLE

        devices = noise_service.list_input_devices()

        if not MICROPHONE_AVAILABLE:
            return JsonResponse(
                {
                    "success": False,
                    "error": "sounddevice not available - running in simulation mode",
                    "devices": [],
                    "microphone_available": False,
                },
                status=200,
            )

        status = noise_service.get_device_status()
        return JsonResponse(
            {
                "success": True,
                "devices": devices,
                "microphone_available": True,
                # What the service is actually capturing from, which is not the
                # same as the saved selection when that one is automatic or no
                # longer resolves.
                "active_index": status["device_index"],
                "active_name": status["device_name"],
                "device_status": status["device_status"],
            }
        )
