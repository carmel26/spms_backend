"""Migration to rename legacy `custom_users` table to `users` if needed.

This uses a RunPython migration to safely detect the existing table
and rename it on MySQL deployments where the physical table name
was not updated when the model's `db_table` option changed.
"""

from django.db import migrations, connection


def forwards_rename(apps, schema_editor):
    """Rename `custom_users` -> `users` if present and `users` missing."""
    cursor = schema_editor.connection.cursor()
    try:
        tables = set(connection.introspection.table_names())
    except Exception:
        # Fallback: if introspection fails, attempt rename and let DB raise if inappropriate
        tables = set()

    if 'custom_users' in tables and 'users' not in tables:
        cursor.execute('RENAME TABLE `custom_users` TO `users`;')


def reverse_rename(apps, schema_editor):
    """Reverse: rename `users` -> `custom_users` if needed."""
    cursor = schema_editor.connection.cursor()
    try:
        tables = set(connection.introspection.table_names())
    except Exception:
        tables = set()

    if 'users' in tables and 'custom_users' not in tables:
        cursor.execute('RENAME TABLE `users` TO `custom_users`;')


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0013_usergroup_blockchain_hash_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards_rename, reverse_rename),
    ]
