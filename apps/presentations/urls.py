from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.presentations.views import PresentationRequestViewSet

router = DefaultRouter()
router.register(r'requests', PresentationRequestViewSet, basename='presentation-request')

urlpatterns = [
    path('', include(router.urls)),
]
