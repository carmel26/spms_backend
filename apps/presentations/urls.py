from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.presentations.views import PresentationRequestViewSet, FormViewSet, SelfAssessmentViewSet

router = DefaultRouter()
router.register(r'requests', PresentationRequestViewSet, basename='presentation-request')
router.register(r'forms', FormViewSet, basename='presentation-form')
router.register(r'self-assessments', SelfAssessmentViewSet, basename='self-assessment')

urlpatterns = [
    path('', include(router.urls)),
]
