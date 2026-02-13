from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.presentations.views import (
    PresentationRequestViewSet, 
    FormViewSet, 
    SelfAssessmentViewSet, 
    ProposalEvaluationViewSet, 
    PhdProposalEvaluationViewSet, 
    PhdAssessmentItemViewSet,
    SupervisorStudentsView,
    ExaminerStudentsView,
    AllStudentsReportView,
    ModeratorPresentationsView,
    ValidatePresentationView,
    PresentationsReportView
)

router = DefaultRouter()
router.register(r'requests', PresentationRequestViewSet, basename='presentation-request')
router.register(r'forms', FormViewSet, basename='presentation-form')
router.register(r'self-assessments', SelfAssessmentViewSet, basename='self-assessment')
router.register(r'proposal-evaluations', ProposalEvaluationViewSet, basename='proposal-evaluation')
router.register(r'phd-proposal-evaluations', PhdProposalEvaluationViewSet, basename='phd-proposal-evaluation')
router.register(r'phd-assessment-items', PhdAssessmentItemViewSet, basename='phd-assessment-item')

urlpatterns = [
    path('', include(router.urls)),
    path('supervisor/students/', SupervisorStudentsView.as_view(), name='supervisor-students'),
    path('examiner/students/', ExaminerStudentsView.as_view(), name='examiner-students'),
    path('reports/all-students/', AllStudentsReportView.as_view(), name='all-students-report'),
    path('reports/presentations/', PresentationsReportView.as_view(), name='presentations-report'),
    path('moderator/presentations/', ModeratorPresentationsView.as_view(), name='moderator-presentations'),
    path('moderator/validate/<uuid:pk>/', ValidatePresentationView.as_view(), name='validate-presentation'),
]
