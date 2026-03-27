"""URL configuration for Touch Piano plugin."""

from django.urls import path

from . import views

app_name = "touch_piano"

urlpatterns = [
    # Dashboard
    path("", views.PianoDashboardView.as_view(), name="dashboard"),
    # Session management
    path("session/start/", views.PianoStartSessionView.as_view(), name="session_start"),
    path("session/stop/", views.PianoStopSessionView.as_view(), name="session_stop"),
    path("session/status/", views.PianoStatusView.as_view(), name="status"),
    # Key press APIs
    path("key/press/", views.PianoKeyPressView.as_view(), name="key_press"),
    path("key/web-press/", views.PianoWebKeyPressView.as_view(), name="web_key_press"),
    # Configuration management
    path("configs/", views.PianoConfigListView.as_view(), name="config_list"),
    path(
        "configs/create/", views.PianoConfigCreateView.as_view(), name="config_create"
    ),
    path(
        "configs/<int:config_id>/edit/",
        views.PianoConfigUpdateView.as_view(),
        name="config_update",
    ),
    path(
        "configs/<int:config_id>/delete/",
        views.PianoConfigDeleteView.as_view(),
        name="config_delete",
    ),
    # Instructions
    path("instructions/", views.PianoInstructionsView.as_view(), name="instructions"),
]
