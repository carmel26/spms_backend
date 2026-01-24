# Generated migration to remove deprecated role fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_add_title_and_multiple_roles'),
    ]

    operations = [
        # Remove deprecated user_group ForeignKey - replaced by user_groups ManyToMany
        migrations.RemoveField(
            model_name='customuser',
            name='user_group',
        ),
        
        # Remove deprecated role CharField if it still exists
        migrations.RemoveField(
            model_name='customuser',
            name='role',
        ),
    ]
