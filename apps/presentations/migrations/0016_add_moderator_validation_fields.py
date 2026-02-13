# Generated migration for moderator validation fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('presentations', '0015_alter_examinerassignment_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='presentationrequest',
            name='moderator_validation_status',
            field=models.CharField(
                blank=True,
                choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                default='pending',
                help_text="Moderator's validation decision for completed presentations",
                max_length=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='presentationrequest',
            name='moderator_validation_comments',
            field=models.TextField(
                blank=True,
                help_text="Moderator's comments on the validation",
                null=True
            ),
        ),
        migrations.AddField(
            model_name='presentationrequest',
            name='moderator_validated_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the moderator validated this presentation',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='presentationrequest',
            name='moderator_validated_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Moderator who validated this presentation',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='validated_presentations',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
