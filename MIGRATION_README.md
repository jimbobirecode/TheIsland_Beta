# Database Migration Required

## Issues Fixed

This update fixes two critical bugs preventing inquiries from being saved and displayed:

### Bug #1: Database Query Mismatch
**Problem**: Inquiries were saved with `club = "demo"` but the API queried for `club = "theisland"`
**Impact**: Inquiries were saved to database but not visible in dashboard
**Fix**: Changed API query to use `DATABASE_CLUB_ID` instead of `DEFAULT_COURSE_ID`

### Bug #2: Invalid Status Constraint
**Problem**: Database only allowed status values: `'provisional', 'confirmed', 'cancelled', 'completed'`
**Impact**: INSERT statements failed with constraint violations because code uses: `'Processing', 'Inquiry', 'Requested', 'Confirmed'`
**Fix**: Updated schema constraint to accept all status values

## Required Actions

### 1. Run Database Migration

Connect to your production PostgreSQL database and run:

```bash
psql $DATABASE_URL -f migration_fix_status_constraint.sql
```

Or manually execute:

```sql
-- Drop the old constraint
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;

-- Add the new constraint with all valid status values
ALTER TABLE bookings ADD CONSTRAINT valid_status
    CHECK (status IN ('Processing', 'Inquiry', 'Requested', 'Confirmed', 'provisional', 'confirmed', 'cancelled', 'completed'));
```

### 2. Deploy Updated Code

The following files have been updated:
- `island_email_bot.py` - Fixed database queries to use correct club ID
- `schema.sql` - Updated for new installations
- `migration_fix_status_constraint.sql` - Migration for existing databases

### 3. Verify Fix

After deploying:

1. Send a test email to: `clubname@bookings.teemail.io`
2. Check application logs for successful save: `✅ BOOKING SAVED`
3. Verify inquiry appears in dashboard with status "Inquiry"
4. Confirm email with tee times is sent to customer

## Status Value Meanings

The system now supports these status values:

- **Processing** - Temporary status while checking availability (< 2 seconds)
- **Inquiry** - Initial inquiry received, available times sent
- **Requested** - Customer clicked "Book Now" and requested specific time
- **Confirmed** - Staff manually confirmed the booking
- **provisional** - (Legacy) Provisional booking
- **confirmed** - (Legacy) Confirmed booking
- **cancelled** - Booking was cancelled
- **completed** - Booking is complete

## Environment Variables

Ensure these are set correctly in Render:

```
DATABASE_CLUB_ID=demo          # For database filtering (dashboard multi-tenancy)
DEFAULT_COURSE_ID=theisland    # For Core API calls (course identifier)
```

These serve different purposes:
- `DATABASE_CLUB_ID` - Used for database queries and multi-tenant filtering
- `DEFAULT_COURSE_ID` - Used for Core API to specify which course to check
