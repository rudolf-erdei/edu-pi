"""Views for Noise Monitor plugin."""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, FormView

from datetime import timedelta

from .forms import ProfileSelectForm, CustomThresholdForm, NoiseMonitorControlForm
from .models import NoiseProfile, NoiseMonitorConfig, NoiseReading
from .noise_service import noise_service

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
            # Create default config with Test profile
            profile, _ = NoiseProfile.objects.get_or_create(
                profile_type=NoiseProfile.ProfileType.TEACHING,
                defaults={
                    "name": "Teaching",
                    "description": "Moderate noise levels for normal teaching",
                    "yellow_threshold": 40,
                    "red_threshold": 70,
                },
            )
            config = NoiseMonitorConfig.objects.create(
                name="Default",
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

        # Recent readings (last 50)
        context["recent_readings"] = NoiseReading.objects.filter(
            config=config
        ).order_by("-timestamp")[:50]

        return context


class NoiseMonitorConfigView(FormView):
    """View for configuring noise monitor."""

    template_name = "noise_monitor/config_form.html"
    form_class = ProfileSelectForm
    success_url = reverse_lazy("noise_monitor:dashboard")

    def get_context_data(self, **kwargs):
        """Add custom threshold form to context."""
        context = super().get_context_data(**kwargs)
        context["custom_form"] = CustomThresholdForm()
        context["profiles"] = NoiseProfile.objects.filter(is_active=True)
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
        config.instant_window_seconds = form.cleaned_data["instant_window_seconds"]
        config.session_window_minutes = form.cleaned_data["session_window_minutes"]
        config.led_brightness = form.cleaned_data["led_brightness"]
        config.save()

        # Update service configuration
        noise_service.configure(
            yellow_threshold=profile.yellow_threshold,
            red_threshold=profile.red_threshold,
            instant_window_seconds=config.instant_window_seconds,
            session_window_minutes=config.session_window_minutes,
            brightness=config.led_brightness,
        )

        logger.info(f"Noise monitor configured with profile: {profile.name}")
        return super().form_valid(form)


class CustomThresholdConfigView(FormView):
    """View for custom threshold configuration."""

    template_name = "noise_monitor/custom_config.html"
    form_class = CustomThresholdForm
    success_url = reverse_lazy("noise_monitor:dashboard")

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
        # Initialize GPIO if not already done
        noise_service.initialize_gpio(
            instant_red_pin=5,
            instant_green_pin=6,
            instant_blue_pin=13,
            session_red_pin=19,
            session_green_pin=26,
            session_blue_pin=16,
        )

        # Get config and configure service
        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        if config:
            noise_service.configure(
                yellow_threshold=config.profile.yellow_threshold
                if config.profile
                else 40,
                red_threshold=config.profile.red_threshold if config.profile else 70,
                instant_window_seconds=config.instant_window_seconds,
                session_window_minutes=config.session_window_minutes,
                brightness=config.led_brightness,
            )

        # Start monitoring
        noise_service.start_monitoring(callback=self._on_noise_update)
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

    def _on_noise_update(self, data):
        """Callback when noise levels update."""
        # Save reading to database
        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        if config:
            try:
                NoiseReading.objects.create(
                    config=config,
                    raw_level=data["instant_average"],  # Use instant as raw
                    instant_average=data["instant_average"],
                    session_average=data["session_average"],
                    instant_color=data["instant_color"],
                    session_color=data["session_color"],
                )
            except Exception as e:
                logger.error(f"Error saving noise reading: {e}")


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
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = []

            for idx, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': idx,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'default_samplerate': int(device['default_samplerate']),
                    })

            return JsonResponse({
                'success': True,
                'devices': input_devices,
                'default_input_index': sd.default.device[0] if sd.default.device[0] is not None else None,
            })
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'sounddevice not available - running in simulation mode',
                'devices': [],
                'default_input_index': None,
            }, status=200)
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'devices': [],
            }, status=500)
