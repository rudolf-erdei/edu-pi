"""URL configuration for Activity Timer plugin."""

from django.urls import path

from . import views

app_name = "activity_timer"

urlpatterns = [
    path("", views.TimerDashboardView.as_view(), name="dashboard"),
    path("control/", views.TimerControlView.as_view(), name="control"),
    path("status/", views.TimerStatusView.as_view(), name="status"),
    path("configs/", views.TimerConfigListView.as_view(), name="config_list"),
    path(
        "configs/create/", views.TimerConfigCreateView.as_view(), name="config_create"
    ),
    path(
        "configs/<int:config_id>/edit/",
        views.TimerConfigUpdateView.as_view(),
        name="config_update",
    ),
    path(
        "configs/<int:config_id>/delete/",
        views.TimerConfigDeleteView.as_view(),
        name="config_delete",
    ),
]
