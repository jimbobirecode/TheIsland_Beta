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
**Fix**: Updated schema constraint to accept all status values (BOTH uppercase and lowercase for backwards compatibility)

## Required Actions

### 1. Check Current Status Values (Optional but Recommended)

First, check what status values currently exist in your database:

```bash
psql $DATABASE_URL -f check_current_status_values.sql
```

This will show you what data exists before migration.

### 2. Run Database Migration

Connect to your production PostgreSQL database and run:

```bash
psql $DATABASE_URL -f migration_fix_status_constraint.sql
```

This migration script will:
1. Show current status values in the database
2. Drop the old constraint
3. Add the new constraint accepting BOTH uppercase and lowercase status values
4. Verify the migration succeeded

**Backwards Compatibility:**
The new constraint accepts **both uppercase AND lowercase** status values:
- ✅ `'Confirmed'` (preferred, used by new code)
- ✅ `'confirmed'` (legacy, for backwards compatibility)
- ✅ `'Booked'`, `'booked'`
- ✅ `'Pending'`, `'pending'`
- etc.

This means **old code using lowercase values will continue to work** without any changes!

### 3. Deploy Updated Code

The following files have been updated:
- `island_email_bot.py` - Fixed database queries to use correct club ID
- `schema.sql` - Updated for new installations
- `migration_fix_status_constraint.sql` - Migration for existing databases

### 4. Verify Fix

After deploying:

1. Send a test email to: `clubname@bookings.teemail.io`
2. Check application logs for successful save: `✅ BOOKING SAVED`
3. Verify inquiry appears in dashboard with status "Inquiry"
4. Confirm email with tee times is sent to customer

## Status Value Meanings

The system now supports these status values:

**Current Flow (New System - Uppercase Preferred):**
- **Processing** - Temporary status while checking availability (< 2 seconds)
- **Inquiry** - Initial inquiry received, available times sent
- **Requested** - Customer clicked "Book Now" and requested specific time
- **Confirmed** - Staff manually confirmed the booking

**Legacy Status Values (Preserved):**
- **Booked** - Legacy booked status
- **Pending** - Legacy pending confirmation
- **Rejected** - Legacy rejected booking
- **Provisional** - Provisional booking (not yet confirmed)
- **Cancelled** - Booking was cancelled
- **Completed** - Booking is complete

**Note:** All status values accept both uppercase and lowercase for backwards compatibility. For example, both `'Confirmed'` and `'confirmed'` are valid. This ensures old codebases continue to work without modifications.

## Environment Variables

Ensure these are set correctly in Render:

```
DATABASE_CLUB_ID=demo          # For database filtering (dashboard multi-tenancy)
DEFAULT_COURSE_ID=theisland    # For Core API calls (course identifier)
```

These serve different purposes:
- `DATABASE_CLUB_ID` - Used for database queries and multi-tenant filtering
- `DEFAULT_COURSE_ID` - Used for Core API to specify which course to check
