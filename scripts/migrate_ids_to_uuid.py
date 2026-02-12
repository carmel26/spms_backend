"""
One-time script to convert existing integer-string IDs in char(32) columns
to proper UUID hex strings (no hyphens, 32 hex chars) after the schema
migration changed PKs from int → UUIDField.

Usage:
    cd backend
    source venv/bin/activate
    python manage.py shell < scripts/migrate_ids_to_uuid.py

This script:
  1. Disables FK checks
  2. For each table whose PK was changed, builds old_id → new_uuid map
  3. Updates the PK column
  4. Updates ALL FK columns that reference that PK
  5. Re-enables FK checks
"""

import uuid
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# ── helpers ──────────────────────────────────────────────────────
def is_valid_uuid_hex(val):
    """Return True if val is already a 32-char hex UUID."""
    if not val or not isinstance(val, str):
        return False
    val = val.replace('-', '')
    if len(val) != 32:
        return False
    try:
        int(val, 16)
        return True
    except ValueError:
        return False


def gen_uuid_hex():
    return uuid.uuid4().hex  # 32-char hex, no hyphens


# ── Discover FK relationships ───────────────────────────────────
cursor.execute('''
    SELECT TABLE_NAME, COLUMN_NAME,
           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND REFERENCED_TABLE_NAME IS NOT NULL
    ORDER BY REFERENCED_TABLE_NAME
''')
fk_rows = cursor.fetchall()

# Build: referenced_table -> [(child_table, child_col, ref_col), ...]
fk_map = {}
for child_tbl, child_col, ref_tbl, ref_col in fk_rows:
    fk_map.setdefault(ref_tbl, []).append((child_tbl, child_col, ref_col))

# ── Tables whose PK (id) was changed to char(32) ───────────────
# We only process tables where the `id` column is char(32).
cursor.execute('''
    SELECT TABLE_NAME
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND COLUMN_NAME = 'id'
      AND COLUMN_TYPE = 'char(32)'
    ORDER BY TABLE_NAME
''')
pk_tables = [r[0] for r in cursor.fetchall()]

# Order matters: parent tables must be processed before children.
# We'll do a topological sort based on FK deps.
# First, figure out which pk_tables depend on other pk_tables via FKs.
pk_set = set(pk_tables)
deps = {t: set() for t in pk_tables}
for t in pk_tables:
    # columns in this table that are FK references to OTHER pk_tables
    cursor.execute('''
        SELECT REFERENCED_TABLE_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND REFERENCED_TABLE_NAME IS NOT NULL
          AND COLUMN_NAME != 'id'
    ''', [t])
    for (ref,) in cursor.fetchall():
        if ref in pk_set and ref != t:
            deps[t].add(ref)

# Simple topological sort
ordered = []
visited = set()


def visit(t):
    if t in visited:
        return
    visited.add(t)
    for d in deps.get(t, []):
        visit(d)
    ordered.append(t)


for t in pk_tables:
    visit(t)

print(f'\n=== Converting {len(ordered)} tables (topological order) ===')
for i, t in enumerate(ordered, 1):
    print(f'  {i}. {t}')

# ── Disable FK checks ──────────────────────────────────────────
cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
print('\nFK checks disabled.')

# ── Global mapping: (table, old_id) → new_uuid_hex ─────────────
all_maps = {}  # table_name -> {old_id_str: new_uuid_hex}

for tbl in ordered:
    cursor.execute(f'SELECT id FROM `{tbl}`')
    rows = cursor.fetchall()
    if not rows:
        print(f'\n[{tbl}] — empty, skipping')
        continue

    id_map = {}
    needs_conversion = False
    for (old_id,) in rows:
        old_str = str(old_id)
        if is_valid_uuid_hex(old_str):
            id_map[old_str] = old_str  # already a UUID
        else:
            id_map[old_str] = gen_uuid_hex()
            needs_conversion = True

    if not needs_conversion:
        print(f'\n[{tbl}] — {len(rows)} rows already have valid UUIDs, skipping')
        all_maps[tbl] = id_map
        continue

    all_maps[tbl] = id_map
    print(f'\n[{tbl}] — converting {len(id_map)} rows')

    # 1) Update FK columns in child tables that reference this table
    children = fk_map.get(tbl, [])
    for child_tbl, child_col, ref_col in children:
        if ref_col != 'id':
            continue
        for old_val, new_val in id_map.items():
            if old_val == new_val:
                continue
            cursor.execute(
                f'UPDATE `{child_tbl}` SET `{child_col}` = %s WHERE `{child_col}` = %s',
                [new_val, old_val]
            )
            affected = cursor.rowcount
            if affected:
                print(f'    {child_tbl}.{child_col}: {old_val} → {new_val} ({affected} rows)')

    # 2) Update self-referencing FK columns in THIS table (e.g. users.approved_by_id -> users.id)
    for child_tbl, child_col, ref_col in children:
        if child_tbl == tbl and ref_col == 'id':
            # already handled above, but the PK hasn't changed yet
            # so we handle self-refs again after PK update below
            pass

    # 3) Update the PK itself
    for old_val, new_val in id_map.items():
        if old_val == new_val:
            continue
        cursor.execute(
            f'UPDATE `{tbl}` SET `id` = %s WHERE `id` = %s',
            [new_val, old_val]
        )

    print(f'    ✓ PK updated for {tbl}')

# ── Handle M2M through tables that might have their own id column ──
# M2M through tables may have an auto-id that is still int; those are
# managed by Django and typically stay as int (they are not in our models).
# No action needed for those.

# ── Re-enable FK checks ────────────────────────────────────────
cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
print('\nFK checks re-enabled.')

# ── Commit ──────────────────────────────────────────────────────
connection.connection.commit()
print('\n✅ All data committed. Migration complete!')
print(f'   Converted {len(ordered)} tables to UUID primary keys.')
