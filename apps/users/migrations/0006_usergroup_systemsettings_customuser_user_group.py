# Generated migration for UserGroup and SystemSettings models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_user_groups(apps, schema_editor):
    """Populate initial user groups"""
    UserGroup = apps.get_model('users', 'UserGroup')
    
    groups = [
        {'name': 'student', 'display_name': 'Student', 'description': 'Student role'},
        {'name': 'supervisor', 'display_name': 'Supervisor', 'description': 'Supervisor role'},
        {'name': 'coordinator', 'display_name': 'Progress Coordinator', 'description': 'Progress Coordinator role'},
        {'name': 'moderator', 'display_name': 'Progress Moderator', 'description': 'Progress Moderator role'},
        {'name': 'examiner', 'display_name': 'Examiner', 'description': 'Examiner role'},
        {'name': 'dean', 'display_name': 'Dean of School', 'description': 'Dean of School role'},
        {'name': 'qa', 'display_name': 'Quality Assurance', 'description': 'QA role'},
        {'name': 'auditor', 'display_name': 'Auditor', 'description': 'Auditor role'},
        {'name': 'admission', 'display_name': 'Admission Officer', 'description': 'Admission Officer role'},
        {'name': 'vice_chancellor', 'display_name': 'Vice Chancellor', 'description': 'Vice Chancellor role'},
        {'name': 'admin', 'display_name': 'Administrator', 'description': 'System administrator'},
    ]
    
    for group_data in groups:
        UserGroup.objects.get_or_create(
            name=group_data['name'],
            defaults={
                'display_name': group_data['display_name'],
                'description': group_data['description'],
                'is_active': True
            }
        )


def migrate_existing_roles(apps, schema_editor):
    """Migrate existing role strings to user_group foreign keys"""
    CustomUser = apps.get_model('users', 'CustomUser')
    UserGroup = apps.get_model('users', 'UserGroup')
    
    # Create a mapping of role strings to user groups
    role_group_map = {}
    for group in UserGroup.objects.all():
        role_group_map[group.name] = group
    
    # Migrate each user's role to the corresponding user_group
    users_updated = 0
    for user in CustomUser.objects.all():
        if user.role:
            # Try to find exact match first
            group = role_group_map.get(user.role)
            
            # If no exact match, try common variations
            if not group:
                # Handle common role variations
                role_mappings = {
                    'progress_coordinator': 'coordinator',
                    'progress_moderator': 'moderator',
                    'quality_assurance': 'qa',
                }
                mapped_role = role_mappings.get(user.role, user.role)
                group = role_group_map.get(mapped_role)
            
            # If still no match, default to 'student'
            if not group:
                print(f"Warning: No matching group for role '{user.role}' (user: {user.username}). Defaulting to 'student'.")
                group = role_group_map.get('student')
            
            if group:
                user.user_group = group
                user.save(update_fields=['user_group'])
                users_updated += 1
    
    print(f"Migrated {users_updated} users to use user_group foreign keys.")


def create_default_settings(apps, schema_editor):
    """Create default system settings"""
    SystemSettings = apps.get_model('users', 'SystemSettings')
    
    SystemSettings.objects.get_or_create(
        pk=1,
        defaults={
            'system_name': 'Secure Progress Management System',
            'system_email': 'admin@nm-aist.ac.tz',
            'system_url': 'http://localhost:4200',
            'max_presentations': 3,
            'presentation_duration': 20,
            'qa_duration': 10,
            'email_on_registration': True,
            'email_on_presentation_request': True,
            'email_on_approval': True,
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0001_initial'),
        ('users', '0005_studentprofile_is_admitted'),
    ]

    operations = [
        # Create UserGroup model
        migrations.CreateModel(
            name='UserGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Role name (e.g., student, supervisor, admin)', max_length=50, unique=True)),
                ('display_name', models.CharField(help_text='Display name for the role', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'user_groups',
                'ordering': ['name'],
            },
        ),
        
        # Populate user groups
        migrations.RunPython(populate_user_groups, migrations.RunPython.noop),
        
        # Add user_group field to CustomUser
        migrations.AddField(
            model_name='customuser',
            name='user_group',
            field=models.ForeignKey(
                blank=True,
                help_text="User's role/group",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='users',
                to='users.usergroup'
            ),
        ),
        
        # Migrate existing roles
        migrations.RunPython(migrate_existing_roles, migrations.RunPython.noop),
        
        # Create SystemSettings model
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_name', models.CharField(default='Secure Progress Management System', max_length=255)),
                ('system_email', models.EmailField(default='admin@nm-aist.ac.tz', max_length=254)),
                ('system_url', models.URLField(default='http://localhost:4200')),
                ('max_presentations', models.IntegerField(default=3, help_text='Maximum presentations per student')),
                ('presentation_duration', models.IntegerField(default=20, help_text='Presentation duration in minutes')),
                ('qa_duration', models.IntegerField(default=10, help_text='Q&A duration in minutes')),
                ('email_on_registration', models.BooleanField(default=True, help_text='Send email on user registration')),
                ('email_on_presentation_request', models.BooleanField(default=True, help_text='Send email on presentation request')),
                ('email_on_approval', models.BooleanField(default=True, help_text='Send email on presentation approval')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='settings_updates',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'system_settings',
                'verbose_name': 'System Settings',
                'verbose_name_plural': 'System Settings',
            },
        ),
        
        # Create default settings
        migrations.RunPython(create_default_settings, migrations.RunPython.noop),
    ]
