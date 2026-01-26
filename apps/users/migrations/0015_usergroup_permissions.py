from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0014_rename_custom_users_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='usergroup',
            name='permissions',
            field=models.JSONField(default=list, blank=True),
        ),
    ]
