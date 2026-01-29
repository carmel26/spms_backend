from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.presentations.views import PresentationRequestViewSet, FormViewSet

router = DefaultRouter()
router.register(r'requests', PresentationRequestViewSet, basename='presentation-request')
router.register(r'forms', FormViewSet, basename='presentation-form')

urlpatterns = [
    path('', include(router.urls)),
]
