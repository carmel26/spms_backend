from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register ViewSets
# Note: Order matters - register more specific routes before the generic empty string pattern
router = DefaultRouter()
router.register(r'students', views.StudentProfileViewSet, basename='student-profile')
router.register(r'groups', views.UserGroupViewSet, basename='user-group')
router.register(r'settings', views.SystemSettingsViewSet, basename='system-settings')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'', views.UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    # Custom action endpoints (these need to be explicit paths for custom actions)
    path('me/', views.UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('register/', views.UserViewSet.as_view({'post': 'register'}), name='user-register'),
    path('login/', views.UserViewSet.as_view({'post': 'login'}), name='user-login'),
    path('change-password/', views.UserViewSet.as_view({'post': 'change_password'}), name='user-change-password'),
    path('supervised_students/', views.UserViewSet.as_view({'get': 'supervised_students'}), name='user-supervised-students'),
    path('student_dashboard/', views.UserViewSet.as_view({'get': 'student_dashboard'}), name='user-student-dashboard'),
    path('supervisor_dashboard/', views.UserViewSet.as_view({'get': 'supervisor_dashboard'}), name='user-supervisor-dashboard'),
    path('coordinator_dashboard/', views.UserViewSet.as_view({'get': 'coordinator_dashboard'}), name='user-coordinator-dashboard'),
    path('examiner_dashboard/', views.UserViewSet.as_view({'get': 'examiner_dashboard'}), name='user-examiner-dashboard'),
    path('admission_dashboard/', views.UserViewSet.as_view({'get': 'admission_dashboard'}), name='user-admission-dashboard'),
    path('admin_dashboard/', views.UserViewSet.as_view({'get': 'admin_dashboard'}), name='user-admin-dashboard'),
    path('<int:pk>/approve/', views.UserViewSet.as_view({'post': 'approve'}), name='user-approve'),
    path('<int:pk>/reject/', views.UserViewSet.as_view({'post': 'reject'}), name='user-reject'),
]
