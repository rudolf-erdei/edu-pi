"""Django views for Touch Piano plugin."""

import json
import logging
from typing import Optional

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from .models import PianoConfig, PianoSession, PianoKey, KeyPress
from .forms import PianoConfigForm, QuickPlayForm
from .piano_service import piano_service, DEFAULT_KEY_MAPPING

logger = logging.getLogger(__name__)


class PianoDashboardView(View):
    """Main dashboard view for the Touch Piano."""

    def get(self, request):
        """Display the piano dashboard."""
        # Get all active piano configurations
        configs = PianoConfig.objects.filter(is_active=True).order_by("name")

        # Get or create default configuration
        default_config = PianoConfig.objects.filter(is_active=True).first()

        if not default_config:
            # Create default configuration with keys
            default_config = self._create_default_config()

        # Get keys for default config
        keys = []
        if default_config:
            keys = list(
                default_config.keys.filter(is_active=True).order_by("key_number")
            )

        # Get current session
        current_session = None
        session_id = piano_service.get_session_id()
        if session_id:
            try:
                current_session = PianoSession.objects.get(
                    id=session_id, is_active=True
                )
            except PianoSession.DoesNotExist:
                pass

        context = {
            "title": _("Touch Piano"),
            "configs": configs,
            "default_config": default_config,
            "keys": keys,
            "current_session": current_session,
            "key_mapping": DEFAULT_KEY_MAPPING,
            "quick_form": QuickPlayForm(),
            "gpio_pins": [4, 7, 20, 21, 12, 2],  # Piano key GPIO pins
        }

        return render(request, "touch_piano/dashboard.html", context)

    def _create_default_config(self) -> Optional[PianoConfig]:
        """Create a default piano configuration with keys."""
        try:
            config = PianoConfig.objects.create(
                name=_("Default Piano"),
                description=_("Standard 6-key piano layout"),
                volume=80,
                sensitivity=5,
                is_active=True,
            )

            # Create keys
            for key_num, key_data in DEFAULT_KEY_MAPPING.items():
                PianoKey.objects.create(
                    config=config,
                    key_number=key_num,
                    note=key_data["note"],
                    frequency=key_data["frequency"],
                    gpio_pin=key_data["gpio_pin"],
                    label=key_data.get("label", ""),
                    color=key_data.get("color", "#3B82F6"),
                    is_active=True,
                )

            logger.info(f"Created default piano configuration: {config.name}")
            return config
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            return None


class PianoStartSessionView(View):
    """View for starting a piano session."""

    @method_decorator(require_POST)
    def post(self, request):
        """Start a new piano session."""
        config_id = request.POST.get("config_id")

        try:
            # Get config
            if config_id:
                config = get_object_or_404(PianoConfig, id=config_id, is_active=True)
            else:
                config = PianoConfig.objects.filter(is_active=True).first()

            if not config:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("No active piano configuration found"),
                    },
                    status=400,
                )

            # End any existing session
            current_session_id = piano_service.get_session_id()
            if current_session_id:
                try:
                    old_session = PianoSession.objects.get(id=current_session_id)
                    old_session.end_session()
                except PianoSession.DoesNotExist:
                    pass

            # Create new session
            session = PianoSession.objects.create(
                config=config,
                is_active=True,
            )

            # Initialize piano service
            key_mapping = {}
            for key in config.keys.filter(is_active=True):
                key_mapping[key.key_number] = {
                    "note": key.note,
                    "frequency": key.frequency,
                    "gpio_pin": key.gpio_pin,
                    "label": key.label,
                    "color": key.color,
                }

            piano_service.set_volume(config.volume)
            piano_service.set_sensitivity(config.sensitivity)
            piano_service.set_session_id(session.id)
            piano_service.initialize_audio(volume=config.volume)
            piano_service.initialize_gpio(key_mapping)
            piano_service.load_note_sounds(key_mapping)
            piano_service.start_monitoring()

            return JsonResponse(
                {
                    "success": True,
                    "session_id": session.id,
                    "message": _("Piano session started"),
                    "config_name": config.name,
                }
            )

        except Exception as e:
            logger.error(f"Error starting piano session: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class PianoStopSessionView(View):
    """View for stopping the piano session."""

    @method_decorator(require_POST)
    def post(self, request):
        """Stop the current piano session."""
        try:
            session_id = piano_service.get_session_id()
            if session_id:
                session = get_object_or_404(PianoSession, id=session_id)
                session.end_session()

            piano_service.cleanup()
            piano_service.set_session_id(None)

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Piano session stopped"),
                }
            )

        except Exception as e:
            logger.error(f"Error stopping piano session: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class PianoStatusView(View):
    """API view for getting current piano status."""

    def get(self, request):
        """Get current piano status."""
        session_id = piano_service.get_session_id()
        key_states = piano_service.get_key_states()

        if session_id:
            try:
                session = PianoSession.objects.get(id=session_id)
                return JsonResponse(
                    {
                        "success": True,
                        "has_active_session": True,
                        "session": {
                            "id": session.id,
                            "config_name": session.config.name
                            if session.config
                            else None,
                            "total_presses": session.total_key_presses,
                            "started_at": session.started_at.isoformat(),
                        },
                        "key_states": key_states,
                    }
                )
            except PianoSession.DoesNotExist:
                pass

        return JsonResponse(
            {
                "success": True,
                "has_active_session": False,
                "key_states": key_states,
            }
        )


class PianoKeyPressView(View):
    """API view for recording key presses from hardware."""

    @method_decorator(require_POST)
    def post(self, request):
        """Record a key press event."""
        try:
            data = json.loads(request.body)
            key_number = data.get("key_number")
            note = data.get("note")
            duration_ms = data.get("duration_ms", 0)

            if not key_number:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Key number is required"),
                    },
                    status=400,
                )

            session_id = piano_service.get_session_id()
            if not session_id:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("No active piano session"),
                    },
                    status=400,
                )

            # Get session and key
            session = get_object_or_404(PianoSession, id=session_id, is_active=True)
            key = None
            try:
                key = PianoKey.objects.get(
                    config=session.config,
                    key_number=key_number,
                    is_active=True,
                )
            except PianoKey.DoesNotExist:
                pass

            # Record key press
            KeyPress.objects.create(
                session=session,
                key=key,
                key_number=key_number,
                note=note or (key.note if key else "Unknown"),
                duration_ms=duration_ms,
            )

            # Update session
            session.increment_presses()

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Key press recorded"),
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "error": _("Invalid JSON"),
                },
                status=400,
            )
        except Exception as e:
            logger.error(f"Error recording key press: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class PianoWebKeyPressView(View):
    """API view for simulating key presses from web interface."""

    @method_decorator(require_POST)
    def post(self, request):
        """Simulate a key press from the web interface."""
        try:
            data = json.loads(request.body)
            key_number = data.get("key_number")
            action = data.get("action", "press")  # 'press' or 'release'

            if not key_number or key_number not in range(1, 7):
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Valid key number (1-6) is required"),
                    },
                    status=400,
                )

            # Check if there's an active session
            session_id = piano_service.get_session_id()
            if not session_id:
                # Initialize a quick session for web play
                piano_service.initialize_audio(volume=80)
                piano_service.initialize_gpio()
                piano_service.load_note_sounds()

            if action == "press":
                piano_service.simulate_key_press(key_number)
            else:
                piano_service.simulate_key_release(key_number)

            return JsonResponse(
                {
                    "success": True,
                    "key_number": key_number,
                    "action": action,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "error": _("Invalid JSON"),
                },
                status=400,
            )
        except Exception as e:
            logger.error(f"Error in web key press: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class PianoConfigListView(View):
    """View for listing piano configurations."""

    def get(self, request):
        """Display list of piano configurations."""
        configs = PianoConfig.objects.all().order_by("-is_active", "name")

        context = {
            "title": _("Piano Configurations"),
            "configs": configs,
        }

        return render(request, "touch_piano/config_list.html", context)


class PianoConfigCreateView(View):
    """View for creating new piano configurations."""

    def get(self, request):
        """Display the configuration form."""
        form = PianoConfigForm()

        context = {
            "title": _("Create Piano Configuration"),
            "form": form,
            "action": _("Create"),
        }

        return render(request, "touch_piano/config_form.html", context)

    def post(self, request):
        """Handle form submission."""
        form = PianoConfigForm(request.POST)

        if form.is_valid():
            config = form.save()

            # Create default keys for this config
            self._create_default_keys(config)

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Configuration created successfully"),
                    "config_id": config.id,
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

    def _create_default_keys(self, config: PianoConfig) -> None:
        """Create default keys for a new configuration."""
        for key_num, key_data in DEFAULT_KEY_MAPPING.items():
            PianoKey.objects.create(
                config=config,
                key_number=key_num,
                note=key_data["note"],
                frequency=key_data["frequency"],
                gpio_pin=key_data["gpio_pin"],
                label=key_data.get("label", ""),
                color=key_data.get("color", "#3B82F6"),
                is_active=True,
            )


class PianoConfigUpdateView(View):
    """View for updating piano configurations."""

    def get(self, request, config_id):
        """Display the configuration form with existing data."""
        config = get_object_or_404(PianoConfig, id=config_id)
        form = PianoConfigForm(instance=config)

        context = {
            "title": _("Edit Piano Configuration"),
            "form": form,
            "config": config,
            "action": _("Update"),
        }

        return render(request, "touch_piano/config_form.html", context)

    def post(self, request, config_id):
        """Handle form submission."""
        config = get_object_or_404(PianoConfig, id=config_id)
        form = PianoConfigForm(request.POST, instance=config)

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


class PianoConfigDeleteView(View):
    """View for deleting piano configurations."""

    @method_decorator(require_POST)
    def post(self, request, config_id):
        """Delete a piano configuration."""
        config = get_object_or_404(PianoConfig, id=config_id)
        config.delete()

        return JsonResponse(
            {
                "success": True,
                "message": _("Configuration deleted successfully"),
            }
        )


class PianoInstructionsView(View):
    """View for displaying piano setup instructions."""

    def get(self, request):
        """Display piano setup instructions."""
        context = {
            "title": _("Piano Setup Instructions"),
            "gpio_pins": [
                {"key": 1, "note": "C4", "pin": 4, "pin_physical": "Pin 7"},
                {"key": 2, "note": "D4", "pin": 7, "pin_physical": "Pin 26"},
                {"key": 3, "note": "E4", "pin": 20, "pin_physical": "Pin 38"},
                {"key": 4, "note": "F4", "pin": 21, "pin_physical": "Pin 40"},
                {"key": 5, "note": "G4", "pin": 12, "pin_physical": "Pin 32"},
                {"key": 6, "note": "A4", "pin": 2, "pin_physical": "Pin 3"},
            ],
            "materials": [
                _("6 bananas or other conductive fruits"),
                _("Aluminum foil or copper tape"),
                _("6 x 1MΩ pull-up resistors (optional for capacitive sensing)"),
                _("Jumper wires"),
                _("Speaker or headphones (3.5mm jack)"),
            ],
            "steps": [
                _("Connect GPIO pins to conductive materials using jumper wires"),
                _(
                    "Connect a 1MΩ resistor between each GPIO pin and ground (for capacitive sensing)"
                ),
                _("Connect speaker/headphones to the 3.5mm audio jack"),
                _("Start a piano session from this dashboard"),
                _("Touch the conductive materials to play notes!"),
            ],
        }

        return render(request, "touch_piano/instructions.html", context)
