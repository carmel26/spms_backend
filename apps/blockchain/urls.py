"""
URL configuration for blockchain app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.blockchain.views import BlockchainViewSet

router = DefaultRouter()
router.register(r'records', BlockchainViewSet, basename='blockchain')

urlpatterns = [
    path('', include(router.urls)),
]
