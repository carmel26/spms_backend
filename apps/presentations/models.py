from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from datetime import timedelta


class PresentationRequest(models.Model):
    """Model for student presentation requests"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    student = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='presentation_requests'
    )
    research_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Proposed research title for this presentation"
    )
    presentation_type = models.ForeignKey(
        'schools.PresentationType',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Documents
    research_document = models.FileField(
        upload_to='presentation_documents/research/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    supervisors = models.ManyToManyField(
        'users.CustomUser',
        related_name='presentation_supervisions',
        blank=True,
        help_text="Proposed supervisors involved in the presentation"
    )
    proposed_examiners = models.ManyToManyField(
        'users.CustomUser',
        related_name='proposed_examiner_presentations',
        blank=True,
        help_text="Proposed examiners for this presentation"
    )
    presentation_slides = models.FileField(
        upload_to='presentation_documents/slides/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'ppt', 'pptx'])]
    )
    plagiarism_report = models.FileField(
        upload_to='presentation_documents/plagiarism/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    
    # Dates
    proposed_date = models.DateTimeField()
    alternative_date = models.DateTimeField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    actual_date = models.DateTimeField(null=True, blank=True)
    
    # Virtual meeting link
    meeting_link = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        help_text="Google Meet or other virtual meeting link"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submission_date = models.DateTimeField(null=True, blank=True)
    viewed_by_coordinators = models.ManyToManyField(
        'users.CustomUser',
        related_name='viewed_presentations',
        blank=True,
        help_text="Coordinators who have viewed this presentation"
    )
    
    # Blockchain hash
    blockchain_hash = models.CharField(max_length=256, blank=True, null=True)
    blockchain_timestamp = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'presentation_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        base = f"{self.student.get_full_name()} - {self.presentation_type.name}"
        return f"{base}: {self.research_title}" if self.research_title else base


class PresentationAssignment(models.Model):
    """Assignments of coordinators and examiners to presentations"""
    
    presentation = models.OneToOneField(
        PresentationRequest,
        on_delete=models.CASCADE,
        related_name='assignment'
    )
    coordinator = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='coordinated_presentations'
    )
    session_moderator = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_presentations',
        help_text="Moderator for the presentation session"
    )
    meeting_link = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        help_text="Google Meet or other virtual meeting link"
    )
    venue = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Physical venue for in-person presentations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'presentation_assignments'
    
    def __str__(self):
        return f"Assignment for {self.presentation}"


class SupervisorAssignment(models.Model):
    """Assignment of supervisors to presentations"""
    
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
    )
    
    assignment = models.ForeignKey(
        PresentationAssignment,
        on_delete=models.CASCADE,
        related_name='supervisor_assignments'
    )
    supervisor = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='assigned'
    )
    acceptance_date = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'supervisor_assignments'
        unique_together = ['assignment', 'supervisor']
    
    def __str__(self):
        return f"{self.supervisor.get_full_name()} - {self.assignment.presentation}"


class ExaminerAssignment(models.Model):
    """Assignment of examiners to presentations"""
    
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
    )
    
    assignment = models.ForeignKey(
        PresentationAssignment,
        on_delete=models.CASCADE,
        related_name='examiner_assignments'
    )
    examiner = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='assigned'
    )
    acceptance_date = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'examiner_assignments'
        unique_together = ['assignment', 'examiner']
    
    def __str__(self):
        return f"{self.examiner.get_full_name()} - {self.assignment.presentation}"


class PresentationSchedule(models.Model):
    """Schedule details for a presentation"""
    
    presentation = models.OneToOneField(
        PresentationRequest,
        on_delete=models.CASCADE,
        related_name='schedule'
    )
    venue = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    meeting_link = models.URLField(blank=True, null=True, help_text="For virtual presentations")
    is_virtual = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'presentation_schedules'
    
    def __str__(self):
        return f"Schedule for {self.presentation}"
    
    def get_remaining_minutes(self):
        """Calculate remaining time until presentation"""
        now = timezone.now()
        if self.start_time > now:
            remaining = self.start_time - now
            return int(remaining.total_seconds() / 60)
        return 0


class ExaminerChangeHistory(models.Model):
    """History of examiner changes for audit trail"""
    
    presentation = models.ForeignKey(
        PresentationRequest,
        on_delete=models.CASCADE,
        related_name='examiner_history'
    )
    changed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='examiner_changes_made'
    )
    previous_examiners = models.ManyToManyField(
        'users.CustomUser',
        related_name='previous_examiner_history',
        blank=True,
        help_text="Examiners before the change"
    )
    new_examiners = models.ManyToManyField(
        'users.CustomUser',
        related_name='new_examiner_history',
        blank=True,
        help_text="Examiners after the change"
    )
    change_reason = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'examiner_change_history'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"Examiner change for {self.presentation} by {self.changed_by.get_full_name()} at {self.changed_at}"


class PresentationAssessment(models.Model):
    """Assessment/feedback from examiners"""
    
    GRADE_CHOICES = (
        ('A', 'Excellent'),
        ('B', 'Good'),
        ('C', 'Satisfactory'),
        ('D', 'Pass'),
        ('F', 'Fail'),
    )
    
    examiner_assignment = models.ForeignKey(
        ExaminerAssignment,
        on_delete=models.CASCADE,
        related_name='assessments'
    )
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    comments = models.TextField()
    recommendations = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'presentation_assessments'
        unique_together = ['examiner_assignment']
    
    def __str__(self):
        return f"Assessment by {self.examiner_assignment.examiner.get_full_name()}"


class Form(models.Model):
    """Generic form submissions related to presentations.

    Stores the entire form payload in a JSON `data` field so the frontend
    can render/edit the form from a single object rather than many columns.
    This model is linked optionally to a `PresentationRequest` and to the
    `BlockchainRecord` for tamper-evident storage when required.
    """

    ROLE_CHOICES = (
        ('student', 'Student'),
        ('supervisor', 'Supervisor'),
        ('examiner', 'Examiner'),
        ('other', 'Other'),
    )

    name = models.CharField(max_length=255, help_text='Human readable form name')
    form_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    presentation = models.ForeignKey(
        PresentationRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='forms',
        help_text='Optional presentation this form is associated with'
    )
    data = models.JSONField(help_text='JSON payload containing the form fields and values')

    created_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='forms_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Link to blockchain record when the form is stored on-chain
    blockchain_record = models.ForeignKey(
        'blockchain.BlockchainRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forms'
    )

    class Meta:
        db_table = 'form'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.form_role}) - {self.created_by.get_full_name()}"


class PhdAssessmentItem(models.Model):
    """Assessment criteria items for PhD Research Proposal Evaluation Form.
    
    These items define the evaluation criteria used by examiners to assess
    PhD research proposals. Admin can manage these items through the settings.
    """
    
    sn = models.PositiveIntegerField(
        help_text='Serial number/order of the assessment item'
    )
    description = models.TextField(
        help_text='Description of the assessment criteria'
    )
    max_score = models.PositiveIntegerField(
        help_text='Maximum score for this assessment item'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this item is currently active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'phd_assessment_items'
        ordering = ['sn']
    
    def __str__(self):
        return f"{self.sn}. {self.description[:50]}... (Max: {self.max_score})"
