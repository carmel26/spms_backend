#!/bin/bash

# Script to send presentation reminders
# This should be run every 5 minutes via cron

cd "$(dirname "$0")"
source venv/bin/activate
python manage.py send_presentation_reminders
