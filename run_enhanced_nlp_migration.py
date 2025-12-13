#!/usr/bin/env python3
"""
Migration Script: Add Enhanced NLP Fields
Run this to add the new fields for comprehensive email parsing
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Apply the enhanced NLP migration"""

    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        sys.exit(1)

    print("=" * 60)
    print("🔧 ENHANCED NLP MIGRATION")
    print("=" * 60)
    print(f"📊 Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print()

    # Read migration SQL
    migration_file = 'migrations/add_enhanced_nlp_fields.sql'

    try:
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
    except FileNotFoundError:
        print(f"❌ ERROR: Migration file not found: {migration_file}")
        sys.exit(1)

    # Connect to database
    print("🔌 Connecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("✅ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Run migration
    print()
    print("🚀 Running migration...")
    print()

    try:
        # Split into individual statements and execute
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]

        for i, statement in enumerate(statements, 1):
            # Skip comments
            if statement.startswith('--'):
                continue

            print(f"   [{i}/{len(statements)}] Executing statement...")
            cursor.execute(statement)

        conn.commit()
        print()
        print("✅ Migration completed successfully!")
        print()

        # Show added columns
        print("📋 New columns added to 'bookings' table:")
        print("   - room_type")
        print("   - contact_name")
        print("   - contact_phone")
        print("   - special_requests[]")
        print("   - dietary_requirements[]")
        print("   - golf_experience")
        print("   - flexible_dates")
        print("   - flexible_times")
        print("   - preferred_time")
        print("   - alternative_times[]")
        print("   - date_confidence")
        print("   - time_confidence")
        print("   - lodging_confidence")
        print()
        print("🎉 Database is now ready for enhanced NLP parsing!")

    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        print(f"   Error code: {e.pgcode}")
        print(f"   Error details: {e.pgerror}")
        sys.exit(1)
    except Exception as e:
        conn.rollback()
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
        print()
        print("🔌 Database connection closed")

if __name__ == '__main__':
    run_migration()
