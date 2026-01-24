from django.db import models


class School(models.Model):
    """School/Faculty Model"""
    
    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    dean = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='school_dean'
    )
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'schools'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Programme(models.Model):
    """Study Programme/Course Model"""
    
    PROGRAMME_TYPE_CHOICES = (
        ('masters', 'Masters'),
        ('phd', 'PhD'),
    )
    
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='programmes'
    )
    programme_type = models.CharField(
        max_length=20,
        choices=PROGRAMME_TYPE_CHOICES
    )
    duration_months = models.IntegerField(default=24)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'programmes'
        unique_together = ['school', 'code']
        ordering = ['school', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.school.abbreviation})"


class PresentationType(models.Model):
    """Types of presentations (e.g., Progress, Final Seminar)"""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    programme_type = models.CharField(
        max_length=20,
        choices=(
            ('masters', 'Masters'),
            ('phd', 'PhD'),
            ('both', 'Both'),
        )
    )
    duration_minutes = models.IntegerField(default=60)
    required_examiners = models.IntegerField(default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'presentation_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name
