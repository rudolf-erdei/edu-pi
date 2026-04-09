from django.urls import path
from .views import check_updates, start_update, get_update_status

urlpatterns = [
    path('check/', check_updates, name='update_check'),
    path('start/', start_update, name='update_start'),
    path('status/', get_update_status, name='update_status'),
]
