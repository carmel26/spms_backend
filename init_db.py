#!/usr/bin/env python3
"""
Script to initialize the MySQL database
"""

import pymysql
import sys

def create_database():
    """Create the database if it doesn't exist"""
    try:
        connection = pymysql.connect(
            host='127.0.0.1',
            user='root',
            password='carmel@1994',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Create database
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS secure_progress_management "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            print("✓ Database 'secure_progress_management' created successfully!")
            
        connection.close()
        return True
        
    except pymysql.err.OperationalError as e:
        print(f"✗ Error connecting to MySQL: {e}")
        print("\nPlease check:")
        print("1. MySQL server is running")
        print("2. Username and password are correct")
        print("3. MySQL is accessible on localhost:3306")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == '__main__':
    print("Initializing MySQL database...")
    if create_database():
        sys.exit(0)
    else:
        sys.exit(1)
