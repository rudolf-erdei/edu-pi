"""URL configuration for Routines plugin."""

from django.urls import path

from . import views

app_name = "routines"

urlpatterns = [
    # Dashboard
    path("", views.RoutinesDashboardView.as_view(), name="dashboard"),
    # Routine CRUD
    path("routines/create/", views.RoutineCreateView.as_view(), name="routine_create"),
    path(
        "routines/<int:routine_id>/edit/",
        views.RoutineUpdateView.as_view(),
        name="routine_update",
    ),
    path(
        "routines/<int:routine_id>/delete/",
        views.RoutineDeleteView.as_view(),
        name="routine_delete",
    ),
    # Player
    path(
        "routines/<int:routine_id>/play/",
        views.RoutinePlayerView.as_view(),
        name="routine_player",
    ),
    # API Endpoints
    path("api/control/", views.RoutineControlView.as_view(), name="routine_control"),
    path("api/status/", views.RoutineStatusView.as_view(), name="routine_status"),
    path("api/tts-test/", views.TTSTestView.as_view(), name="tts_test"),
    path(
        "api/presenter-status/",
        views.PresenterStatusView.as_view(),
        name="presenter_status",
    ),
    # Categories
    path(
        "categories/",
        views.RoutineCategoryListView.as_view(),
        name="category_list",
    ),
    path(
        "categories/create/",
        views.RoutineCategoryCreateView.as_view(),
        name="category_create",
    ),
]
