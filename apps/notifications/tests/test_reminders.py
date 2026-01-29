from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from apps.users.models import CustomUser
from apps.presentations.models import PresentationRequest, PresentationSchedule, PresentationAssignment
from apps.schools.models import PresentationType


class ReminderTests(TestCase):
    def setUp(self):
        # create users
        self.student = CustomUser.objects.create_user(username='student1', email='nkeshipelagie@gmail.com', password='pass')
        self.coordinator = CustomUser.objects.create_user(username='coord', email='nkuridiegue@gmail.com', password='pass')
        self.examiner = CustomUser.objects.create_user(username='exam1', email='dieguecarmel@gmail.com', password='pass')

        # minimal presentation request
        # ensure a presentation type exists
        ptype, _ = PresentationType.objects.get_or_create(name='Thesis Defense')
        self.presentation = PresentationRequest.objects.create(
            student=self.student,
            research_title='Test Presentation',
            presentation_type=ptype,
            proposed_date=timezone.now() + timezone.timedelta(minutes=15),
            research_document='dummy.pdf',
            presentation_slides='slides.pdf'
        )

        # create assignment and examiner assignment
        self.assignment = PresentationAssignment.objects.create(presentation=self.presentation, coordinator=self.coordinator)
        # create schedule 15 minutes from now
        self.schedule = PresentationSchedule.objects.create(
            presentation=self.presentation,
            venue='Room 101',
            start_time=timezone.now() + timezone.timedelta(minutes=15),
            end_time=timezone.now() + timezone.timedelta(minutes=45)
        )

    @patch('apps.notifications.utils.EmailMultiAlternatives.send')
    def test_send_presentation_time_reminder_sends_emails(self, mock_send):
        # Import here to ensure models are ready
        from apps.notifications.utils import send_presentation_time_reminder

        # Call the reminder function
        send_presentation_time_reminder(self.presentation, minutes_before=15)

        # Emails attempted to be sent at least once (one per recipient with email)
        self.assertTrue(mock_send.called)