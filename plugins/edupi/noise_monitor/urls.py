"""URL configuration for Noise Monitor plugin."""

from django.urls import path

from . import views

app_name = "noise_monitor"

urlpatterns = [
    path("", views.NoiseMonitorDashboardView.as_view(), name="dashboard"),
    # The history card on its own, which the dashboard re-fetches to keep the
    # graph current. Not under api/: it is a piece of page, not data.
    path("chart/", views.NoiseHistoryChartView.as_view(), name="history_chart"),
    path("config/", views.NoiseMonitorConfigView.as_view(), name="config"),
    path(
        "config/custom/",
        views.CustomThresholdConfigView.as_view(),
        name="custom_config",
    ),
    # Management of the profile list itself. One profile exists per type, so
    # these are addressed by primary key.
    path(
        "profiles/<int:pk>/rename/",
        views.NoiseProfileRenameView.as_view(),
        name="profile_rename",
    ),
    path(
        "profiles/<int:pk>/delete/",
        views.NoiseProfileDeleteView.as_view(),
        name="profile_delete",
    ),
    path("control/", views.NoiseMonitorControlView.as_view(), name="control"),
    path("api/level/", views.NoiseLevelAPIView.as_view(), name="api_level"),
    path("api/history/", views.NoiseHistoryAPIView.as_view(), name="api_history"),
    path("api/audio-devices/", views.AudioDevicesAPIView.as_view(), name="api_audio_devices"),
]
