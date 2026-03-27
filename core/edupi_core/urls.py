"""
URL configuration for the Tinko core application.
"""

from django.urls import path
from . import views

app_name = "edupi_core"

urlpatterns = [
    path("", views.home_view, name="home"),
]
