#!/usr/bin/env python3
"""
Database Migration Runner
Applies the Direct Debit statuses migration to the database
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

def run_migration():
    """Apply the Direct Debit statuses migration"""

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        return False

    print("=" * 60)
    print("🔄 Running Database Migration: Add Direct Debit Statuses")
    print("=" * 60)

    try:
        # Connect to database
        print("\n📡 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("✅ Connected")

        # Read migration file
        print("\n📄 Reading migration file...")
        with open('migrations/add_direct_debit_statuses.sql', 'r') as f:
            migration_sql = f.read()
        print("✅ Migration file loaded")

        # Execute migration
        print("\n⚙️  Applying migration...")

        # Split by semicolons and execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"  Executing statement {i}/{len(statements)}...")
                cursor.execute(statement)

        # Commit changes
        conn.commit()
        print("✅ Migration applied successfully")

        # Verify the constraint
        print("\n🔍 Verifying constraint...")
        cursor.execute("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'valid_status';
        """)
        result = cursor.fetchone()
        if result:
            print(f"✅ Constraint verified: {result[0][:100]}...")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print("\nThe database now accepts these new statuses:")
        print("  - Pending SEPA (for SEPA Direct Debit payments)")
        print("  - Pending BACS (for BACS Direct Debit payments)")
        print("\n")

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        if conn:
            conn.rollback()
        return False

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
