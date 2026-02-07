#!/usr/bin/env python3
"""
Database Migration Runner
Applies pending SQL migrations to the database
"""

import os
import psycopg2
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def get_database_url():
    """Get database URL from environment"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url or db_url == 'postgresql://user:password@host:port/database':
        raise ValueError("DATABASE_URL not configured. Please set it in your environment or .env file")
    return db_url

def run_migration(cursor, migration_file):
    """Run a single migration file"""
    logging.info(f"Running migration: {migration_file.name}")

    with open(migration_file, 'r') as f:
        sql = f.read()

    try:
        cursor.execute(sql)
        logging.info(f"✅ Successfully applied: {migration_file.name}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to apply {migration_file.name}: {e}")
        return False

def main():
    """Main migration runner"""
    try:
        # Connect to database
        db_url = get_database_url()
        logging.info("Connecting to database...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        logging.info("✅ Connected to database")

        # Find all migration files
        migrations_dir = Path(__file__).parent / 'migrations'
        migration_files = sorted(migrations_dir.glob('*.sql'))

        if not migration_files:
            logging.warning("No migration files found in migrations/ directory")
            return

        logging.info(f"Found {len(migration_files)} migration file(s)")

        # Run each migration
        success_count = 0
        for migration_file in migration_files:
            if run_migration(cursor, migration_file):
                success_count += 1

        # Commit all changes
        conn.commit()
        logging.info(f"✅ Applied {success_count}/{len(migration_files)} migrations successfully")

        cursor.close()
        conn.close()

    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise

if __name__ == '__main__':
    main()
