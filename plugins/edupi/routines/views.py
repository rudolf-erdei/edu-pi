"""Django views for Routines plugin."""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from .models import Routine, RoutineCategory, RoutineSession
from .forms import RoutineForm, RoutineCategoryForm, TTSTestForm
from .services.routine_player import routine_player
from .services.tts_manager import tts_manager

logger = logging.getLogger(__name__)


class RoutinesDashboardView(View):
    """Main dashboard view for Routines."""

    def get(self, request):
        """Display the routines dashboard."""
        # Get categories with their routines
        categories = RoutineCategory.objects.filter(is_active=True).order_by("order")

        # Get all active routines grouped by category
        routines_by_category = {}
        for category in categories:
            routines = Routine.objects.filter(
                category=category, is_active=True
            ).order_by("title")
            if routines.exists():
                routines_by_category[category] = routines

        # Get routines without category
        uncategorized = Routine.objects.filter(
            category=None, is_active=True, is_pre_built=False
        ).order_by("title")

        # Get active session if any
        active_session = routine_player.get_session()

        context = {
            "title": _("Routines"),
            "categories": categories,
            "routines_by_category": routines_by_category,
            "uncategorized": uncategorized,
            "active_session": active_session,
            "is_playing": routine_player.is_playing(),
            "is_paused": routine_player.is_paused(),
        }
        return render(request, "routines/dashboard.html", context)


class RoutinePlayerView(View):
    """View for playing a routine."""

    def get(self, request, routine_id):
        """Display the routine player."""
        routine = get_object_or_404(Routine, id=routine_id, is_active=True)
        lines = routine.get_lines()

        # TODO: SCREEN - Initialize screen display for external display
        # This would integrate with the external screen API when available
        logger.info(f"TODO: SCREEN - Initialize display for routine: {routine.title}")

        context = {
            "title": routine.title,
            "routine": routine,
            "lines": lines,
            "line_count": len(lines),
            "has_audio": routine.has_custom_audio(),
        }
        return render(request, "routines/player.html", context)


class RoutineCreateView(View):
    """View for creating new routines."""

    def get(self, request):
        """Display the create form."""
        form = RoutineForm()
        tts_test_form = TTSTestForm()

        context = {
            "title": _("Create Routine"),
            "form": form,
            "tts_test_form": tts_test_form,
            "action": _("Create"),
        }
        return render(request, "routines/routine_form.html", context)

    def post(self, request):
        """Handle form submission."""
        form = RoutineForm(request.POST, request.FILES)

        if form.is_valid():
            routine = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Routine created successfully"),
                    "routine_id": routine.id,
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


class RoutineUpdateView(View):
    """View for updating routines."""

    def get(self, request, routine_id):
        """Display the edit form."""
        routine = get_object_or_404(Routine, id=routine_id)
        form = RoutineForm(instance=routine)
        tts_test_form = TTSTestForm()

        context = {
            "title": _("Edit Routine"),
            "form": form,
            "tts_test_form": tts_test_form,
            "routine": routine,
            "action": _("Update"),
        }
        return render(request, "routines/routine_form.html", context)

    def post(self, request, routine_id):
        """Handle form submission."""
        routine = get_object_or_404(Routine, id=routine_id)
        form = RoutineForm(request.POST, request.FILES, instance=routine)

        if form.is_valid():
            form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Routine updated successfully"),
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


class RoutineDeleteView(View):
    """View for deleting routines."""

    @method_decorator(require_POST)
    def post(self, request, routine_id):
        """Delete a routine."""
        routine = get_object_or_404(Routine, id=routine_id)
        routine.delete()

        return JsonResponse(
            {
                "success": True,
                "message": _("Routine deleted successfully"),
            }
        )


class RoutineControlView(View):
    """API view for routine playback control."""

    @method_decorator(require_POST)
    def post(self, request):
        """Handle playback control actions."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST

        action = data.get("action")
        routine_id = data.get("routine_id")

        logger.info(f"Routine action: {action}, routine_id: {routine_id}")

        try:
            if action == "start":
                return self._start_routine(routine_id)
            elif action == "play":
                return self._play()
            elif action == "pause":
                return self._pause()
            elif action == "resume":
                return self._resume()
            elif action == "stop":
                return self._stop()
            elif action == "next":
                return self._next_line()
            elif action == "prev":
                return self._prev_line()
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Invalid action"),
                    },
                    status=400,
                )

        except Exception as e:
            logger.error(f"Error handling routine action {action}: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )

    def _start_routine(self, routine_id):
        """Start a new routine session."""
        routine = get_object_or_404(Routine, id=routine_id, is_active=True)

        # Stop any current session
        if routine_player.get_session():
            routine_player.stop()

        # Create new session
        session = RoutineSession.objects.create(
            routine=routine,
            status=RoutineSession.Status.PENDING,
        )

        # Load and preload audio
        routine_player.load_routine(
            session,
            on_line_change=self._on_line_change,
            on_status_change=self._on_status_change,
        )

        # TODO: SCREEN - Display routine title on external screen
        logger.info(f"TODO: SCREEN - Display title: {routine.title}")

        return JsonResponse(
            {
                "success": True,
                "session_id": session.id,
                "routine_id": routine.id,
                "total_lines": routine.get_line_count(),
                "message": _("Routine started"),
            }
        )

    def _play(self):
        """Start or resume playback."""
        success = routine_player.play()
        return JsonResponse(
            {
                "success": success,
                "message": _("Playing") if success else _("Failed to play"),
            }
        )

    def _pause(self):
        """Pause playback."""
        success = routine_player.pause()
        return JsonResponse(
            {
                "success": success,
                "message": _("Paused") if success else _("Failed to pause"),
            }
        )

    def _resume(self):
        """Resume playback."""
        success = routine_player.resume()
        return JsonResponse(
            {
                "success": success,
                "message": _("Resumed") if success else _("Failed to resume"),
            }
        )

    def _stop(self):
        """Stop playback."""
        success = routine_player.stop()

        # TODO: SCREEN - Clear external screen
        logger.info("TODO: SCREEN - Clear display")

        return JsonResponse(
            {
                "success": success,
                "message": _("Stopped") if success else _("Failed to stop"),
            }
        )

    def _next_line(self):
        """Advance to next line."""
        success = routine_player.next_line()
        return JsonResponse(
            {
                "success": success,
                "message": _("Next line") if success else _("At end"),
            }
        )

    def _prev_line(self):
        """Go to previous line."""
        success = routine_player.prev_line()
        return JsonResponse(
            {
                "success": success,
                "message": _("Previous line") if success else _("At beginning"),
            }
        )

    def _on_line_change(self, line_index, line_text):
        """Callback when line changes."""
        # TODO: SCREEN - Update external display with current line
        logger.info(f"TODO: SCREEN - Display line {line_index}: {line_text[:50]}...")

        # Could emit WebSocket event here for real-time sync
        pass

    def _on_status_change(self, status):
        """Callback when playback status changes."""
        logger.debug(f"Routine status changed to: {status}")


class RoutineStatusView(View):
    """API view for getting current routine status."""

    def get(self, request):
        """Get current playback status."""
        session = routine_player.get_session()

        if session:
            current_line = routine_player.get_current_line()
            current, total, percent = routine_player.get_progress()

            return JsonResponse(
                {
                    "success": True,
                    "has_active_session": True,
                    "session": {
                        "id": session.id,
                        "routine_id": session.routine.id,
                        "routine_title": session.routine.title,
                        "status": session.status,
                        "status_display": session.get_status_display(),
                        "current_line_index": current,
                        "total_lines": total,
                        "progress_percent": percent,
                        "current_line": current_line,
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


class TTSTestView(View):
    """API view for testing TTS."""

    async def post(self, request):
        """Generate TTS preview audio."""
        form = TTSTestForm(request.POST)

        if not form.is_valid():
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                },
                status=400,
            )

        text = form.cleaned_data["text"]
        engine = form.cleaned_data["engine"]
        language = form.cleaned_data["language"]
        voice = form.cleaned_data["voice"] or None
        speed = form.cleaned_data["speed"]

        try:
            audio_path = await tts_manager.generate_audio(
                text=text,
                engine_name=engine,
                language=language,
                voice=voice,
                speed=speed,
            )

            if audio_path:
                return JsonResponse(
                    {
                        "success": True,
                        "audio_path": audio_path,
                        "message": _("TTS audio generated successfully"),
                    }
                )
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Failed to generate TTS audio"),
                    },
                    status=500,
                )

        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class RoutineCategoryListView(View):
    """View for listing routine categories."""

    def get(self, request):
        """Display list of categories."""
        categories = RoutineCategory.objects.all().order_by("order")

        context = {
            "title": _("Routine Categories"),
            "categories": categories,
        }
        return render(request, "routines/category_list.html", context)


class RoutineCategoryCreateView(View):
    """View for creating routine categories."""

    def get(self, request):
        """Display the create form."""
        form = RoutineCategoryForm()
        context = {
            "title": _("Create Category"),
            "form": form,
        }
        return render(request, "routines/category_form.html", context)

    def post(self, request):
        """Handle form submission."""
        form = RoutineCategoryForm(request.POST)

        if form.is_valid():
            form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": _("Category created successfully"),
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


class PresenterStatusView(View):
    """API view for presenter status."""

    def get(self, request):
        """Get USB presenter connection status."""
        from .services.presenter_handler import presenter_handler

        return JsonResponse(
            {
                "success": True,
                "available": presenter_handler.is_available(),
                "connected": presenter_handler.is_connected(),
                "device_name": presenter_handler.get_device_name(),
                "monitoring": presenter_handler.is_monitoring(),
            }
        )
