from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.presentations.views import PresentationRequestViewSet, FormViewSet, SelfAssessmentViewSet, ProposalEvaluationViewSet, PhdProposalEvaluationViewSet, PhdAssessmentItemViewSet

router = DefaultRouter()
router.register(r'requests', PresentationRequestViewSet, basename='presentation-request')
router.register(r'forms', FormViewSet, basename='presentation-form')
router.register(r'self-assessments', SelfAssessmentViewSet, basename='self-assessment')
router.register(r'proposal-evaluations', ProposalEvaluationViewSet, basename='proposal-evaluation')
router.register(r'phd-proposal-evaluations', PhdProposalEvaluationViewSet, basename='phd-proposal-evaluation')
router.register(r'phd-assessment-items', PhdAssessmentItemViewSet, basename='phd-assessment-item')

urlpatterns = [
    path('', include(router.urls)),
]
