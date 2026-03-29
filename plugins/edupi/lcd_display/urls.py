"""URL configuration for LCD Display plugin."""

from django.urls import path
from . import views

app_name = "lcd_display"

urlpatterns = [
    path("", views.LCDDisplayView.as_view(), name="index"),
    path("api/show-smile/", views.ShowSmileView.as_view(), name="show_smile"),
    path("api/show-text/", views.ShowTextView.as_view(), name="show_text"),
    path("api/clear/", views.ClearScreenView.as_view(), name="clear_screen"),
    path("api/set-backlight/", views.SetBacklightView.as_view(), name="set_backlight"),
    path("api/set-mood/", views.SetMoodView.as_view(), name="set_mood"),
    path("api/get-mood/", views.GetMoodView.as_view(), name="get_mood"),
]
