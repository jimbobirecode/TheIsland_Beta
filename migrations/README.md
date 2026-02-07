# Database Migrations

This directory contains SQL migration files for the booking system database.

## Running Migrations

### Option 1: Using the Migration Runner Script

```bash
# Make sure DATABASE_URL is set in your environment
python3 run_migrations.py
```

### Option 2: Manual Application via Render Dashboard

1. Go to your Render dashboard
2. Navigate to your PostgreSQL database
3. Open the Shell/Connect tab
4. Copy and paste the SQL from the migration file
5. Execute the SQL

### Option 3: Using psql Command Line

```bash
# If you have psql installed locally and DATABASE_URL configured
psql $DATABASE_URL -f migrations/add_content_field.sql
```

## Migration Files

- `add_booking_form_fields.sql` - Adds lead_name, caddie_requirements, fb_requirements, special_requests columns
- `add_content_field.sql` - Adds content column for additional booking information

## Creating New Migrations

1. Create a new `.sql` file in this directory with a descriptive name
2. Use `IF NOT EXISTS` clauses to make migrations idempotent
3. Add comments documenting what the migration does
4. Test locally before applying to production

## Notes

- All migrations use `IF NOT EXISTS` / `IF EXISTS` to be idempotent (safe to run multiple times)
- The migration runner applies all `.sql` files in alphabetical order
- Always backup your database before running migrations in production
