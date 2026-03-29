"""Views for LCD Display plugin."""

import logging

from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.translation import gettext as _

from .forms import LCDConfigForm, ShowTextForm
from .models import LCDConfig, DisplaySession
from .lcd_service import lcd_service

logger = logging.getLogger(__name__)


class LCDDisplayView(TemplateView):
    """Main LCD display control view."""

    template_name = "lcd_display/index.html"

    def get_context_data(self, **kwargs):
        """Add LCD config and status to context."""
        context = super().get_context_data(**kwargs)

        # Get or create default config
        config, created = LCDConfig.objects.get_or_create(
            name="Default",
            defaults={
                "rotation": LCDConfig.Rotation.ROTATION_0,
                "backlight": 100,
                "contrast": 1.0,
            },
        )

        context["config"] = config
        context["is_initialized"] = lcd_service.is_initialized()
        context["resolution"] = lcd_service.get_resolution()
        context["config_form"] = LCDConfigForm(instance=config)
        context["text_form"] = ShowTextForm()

        return context


class ShowSmileView(View):
    """API view to display smiley face on LCD."""

    def post(self, request):
        """Display smiley face and resume animation."""
        try:
            # Initialize LCD if not already done
            if not lcd_service.is_initialized():
                config = LCDConfig.objects.filter(name="Default").first()
                if config:
                    lcd_service.initialize(
                        rotation=config.rotation,
                        backlight=config.backlight,
                    )
                else:
                    lcd_service.initialize()

            # Resume animation if it was paused
            if not lcd_service.is_animation_running():
                lcd_service.start_face_animation()
            else:
                lcd_service.resume_face_animation()

            # Create session record
            DisplaySession.objects.create(
                mode=DisplaySession.DisplayMode.SMILE,
                is_active=True,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Smiley face animation started"),
                }
            )
        except Exception as e:
            logger.error(f"Error showing smiley face: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class ShowTextView(View):
    """API view to display text on LCD."""

    def post(self, request):
        """Display text on LCD."""
        form = ShowTextForm(request.POST)
        if not form.is_valid():
            return JsonResponse(
                {
                    "success": False,
                    "error": form.errors,
                },
                status=400,
            )

        try:
            text = form.cleaned_data["text"]

            # Initialize LCD if not already done
            if not lcd_service.is_initialized():
                config = LCDConfig.objects.filter(name="Default").first()
                if config:
                    lcd_service.initialize(
                        rotation=config.rotation,
                        backlight=config.backlight,
                    )
                else:
                    lcd_service.initialize()

            # Show text
            lcd_service.show_text(text)

            # Create session record
            DisplaySession.objects.create(
                mode=DisplaySession.DisplayMode.TEXT,
                content=text,
                is_active=True,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Text displayed"),
                }
            )
        except Exception as e:
            logger.error(f"Error showing text: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class ClearScreenView(View):
    """API view to clear LCD screen."""

    def post(self, request):
        """Clear the LCD screen."""
        try:
            if lcd_service.is_initialized():
                lcd_service.clear_screen()

                # Create session record
                DisplaySession.objects.create(
                    mode=DisplaySession.DisplayMode.CLEAR,
                    is_active=True,
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Screen cleared"),
                }
            )
        except Exception as e:
            logger.error(f"Error clearing screen: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class SetBacklightView(View):
    """API view to set LCD backlight brightness."""

    def post(self, request):
        """Set backlight brightness."""
        try:
            brightness = request.POST.get("brightness", "100")
            brightness = int(brightness)
            brightness = max(0, min(100, brightness))

            if lcd_service.is_initialized():
                lcd_service.set_backlight(brightness)

            # Update config
            config = LCDConfig.objects.filter(name="Default").first()
            if config:
                config.backlight = brightness
                config.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Backlight set to %(brightness)s%%")
                    % {"brightness": brightness},
                    "brightness": brightness,
                }
            )
        except Exception as e:
            logger.error(f"Error setting backlight: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )
