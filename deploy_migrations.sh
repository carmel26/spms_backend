#!/bin/bash
# PythonAnywhere Deployment Script for Migrations
# Save this as: deploy_migrations.sh
# Run on PythonAnywhere with: bash deploy_migrations.sh

echo "========================================="
echo "PythonAnywhere Migration Deployment"
echo "========================================="
echo ""

# Activate virtual environment
echo "1. Activating virtual environment..."
source ~/.virtualenvs/venv/bin/activate

# Navigate to project directory
echo "2. Navigating to project directory..."
cd ~/secure-progress-management/backend || cd ~/spms/backend || cd ~/backend

echo ""
echo "3. Current directory: $(pwd)"
echo ""

# Check database connection
echo "4. Testing database connection..."
python manage.py check --database default

if [ $? -ne 0 ]; then
    echo "ERROR: Cannot connect to database. Check your .env settings."
    exit 1
fi

echo ""
echo "5. Showing current migration status..."
python manage.py showmigrations

echo ""
echo "========================================="
echo "Starting Migration Process"
echo "========================================="
echo ""

# Migrate in order: users first (creates user_groups table)
echo "6. Migrating users app (creates user_groups tables)..."
python manage.py migrate users

if [ $? -ne 0 ]; then
    echo "WARNING: Users migration failed. Checking if tables exist..."
    python manage.py dbshell <<EOF
SHOW TABLES LIKE '%users%';
EOF
    
    echo ""
    echo "Attempting to fake problematic migrations..."
    python manage.py migrate users 0009 --fake
    python manage.py migrate users
fi

echo ""
echo "7. Migrating auth app..."
python manage.py migrate auth

echo ""
echo "8. Migrating contenttypes..."
python manage.py migrate contenttypes

echo ""
echo "9. Migrating sessions..."
python manage.py migrate sessions

echo ""
echo "10. Migrating other core apps..."
python manage.py migrate admin
python manage.py migrate authtoken

echo ""
echo "11. Migrating custom apps..."
python manage.py migrate schools
python manage.py migrate blockchain
python manage.py migrate notifications
python manage.py migrate reports

echo ""
echo "12. Migrating presentations (may need faking)..."
# Check if moderator_validation_count exists
TABLE_CHECK=$(python manage.py dbshell <<EOF
SELECT COUNT(*) as col_exists 
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'presentation_requests' 
AND COLUMN_NAME = 'moderator_validation_count';
EOF
)

if echo "$TABLE_CHECK" | grep -q "1"; then
    echo "moderator_validation_count field exists, faking migrations 0018 and 0019..."
    python manage.py migrate presentations 0018 --fake
    python manage.py migrate presentations 0019 --fake
fi

python manage.py migrate presentations

echo ""
echo "13. Running all remaining migrations..."
python manage.py migrate

echo ""
echo "========================================="
echo "Verification"
echo "========================================="
echo ""

echo "14. Final migration status:"
python manage.py showmigrations | grep "\[ \]" | wc -l | xargs -I {} echo "{} unapplied migrations remaining"

echo ""
echo "15. Checking database tables..."
python manage.py dbshell <<EOF
SELECT COUNT(*) as table_count FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = DATABASE();
EOF

echo ""
echo "16. Checking users_groups table..."
python manage.py dbshell <<EOF
SHOW TABLES LIKE '%users_groups%';
DESCRIBE users_groups;
EOF

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Go to PythonAnywhere Web tab"
echo "2. Click 'Reload upendo.pythonanywhere.com'"
echo "3. Check error logs if issues persist:"
echo "   /var/log/upendo.pythonanywhere.com.error.log"
echo ""
