from celery import shared_task
from django.core.mail import send_mail

@shared_task
def test_email():
    send_mail(
        subject='SPMS Test Email',
        message='Celery + Redis is working!',
        from_email='carmelnkeshimana2020@gmail.com',
        recipient_list=['nkeshimanac@nm-aist.ac.tz'],
        fail_silently=False,
    )
