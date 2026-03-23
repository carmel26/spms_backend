# Generated migration for adding priority fields to PresentationType

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='presentationtype',
            name='masters_priority',
            field=models.IntegerField(
                default=0,
                help_text='Display order for Masters students (lower = earlier). 0 means no specific order.'
            ),
        ),
        migrations.AddField(
            model_name='presentationtype',
            name='phd_priority',
            field=models.IntegerField(
                default=0,
                help_text='Display order for PhD students (lower = earlier). 0 means no specific order.'
            ),
        ),
    ]
