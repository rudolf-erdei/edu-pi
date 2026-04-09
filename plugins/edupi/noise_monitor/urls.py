"""URL configuration for Noise Monitor plugin."""

from django.urls import path

from . import views

app_name = "noise_monitor"

urlpatterns = [
    path("", views.NoiseMonitorDashboardView.as_view(), name="dashboard"),
    path("config/", views.NoiseMonitorConfigView.as_view(), name="config"),
    path(
        "config/custom/",
        views.CustomThresholdConfigView.as_view(),
        name="custom_config",
    ),
    path("control/", views.NoiseMonitorControlView.as_view(), name="control"),
    path("api/level/", views.NoiseLevelAPIView.as_view(), name="api_level"),
    path("api/history/", views.NoiseHistoryAPIView.as_view(), name="api_history"),
    path("api/audio-devices/", views.AudioDevicesAPIView.as_view(), name="api_audio_devices"),
]
