from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet, NotificationPreferenceViewSet,
    SendReminderView, BulkSessionReminderView, ReminderHistoryView,
)


router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')

urlpatterns = [
    path('send-reminder/', SendReminderView.as_view(), name='send-reminder'),
    path('reminders/bulk-send/', BulkSessionReminderView.as_view(), name='bulk-session-reminder'),
    path('reminders/history/', ReminderHistoryView.as_view(), name='reminder-history'),
    path('', include(router.urls))
]
