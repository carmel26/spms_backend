from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SchoolViewSet, ProgrammeViewSet, PresentationTypeViewSet

router = DefaultRouter()
router.register(r'schools', SchoolViewSet, basename='school')
router.register(r'programmes', ProgrammeViewSet, basename='programme')
router.register(r'presentation-types', PresentationTypeViewSet, basename='presentation-type')

urlpatterns = [
    path('', include(router.urls)),
]
