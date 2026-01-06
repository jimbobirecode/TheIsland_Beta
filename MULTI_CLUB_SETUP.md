# Multi-Club Booking System

The Island Beta booking system now supports multiple clubs using URL-based routing. Each club has its own booking path, making it easy to manage multiple golf clubs from a single installation.

## URL Structure

Each club gets its own booking URL using this format:

```
https://bookings.teemail.io/<club-id>/book
```

### Examples

- **The Island Golf Club**: `https://bookings.teemail.io/theisland/book`
- **Lahinch Golf Club**: `https://bookings.teemail.io/lahinch/book`
- **Adare Manor**: `https://bookings.teemail.io/adare/book`

## How It Works

### 1. Booking Links in Emails

When a customer receives an inquiry email with available tee times, each "Book Now" button contains the club identifier in the URL:

```html
https://bookings.teemail.io/theisland/book?booking_id=ISL-...&date=2026-01-15&time=10:00&players=4&email=customer@example.com
```

The system automatically:
- Extracts the club ID from the URL path (`theisland`)
- Displays the booking form with club-specific branding
- Submits the form to the club-specific endpoint
- Stores the club ID in the database with the booking

### 2. Database Storage

Each booking is tagged with its club ID in the `bookings` table:

```sql
INSERT INTO bookings (booking_id, club, guest_email, ...)
VALUES ('ISL-20260115-ABC123', 'theisland', 'customer@example.com', ...);
```

### 3. Dashboard Filtering

The dashboard filters bookings by club using the `DATABASE_CLUB_ID` environment variable, showing only bookings for that specific club.

## Configuration

### Single Club Setup

If you're running a single club, set these environment variables:

```bash
DATABASE_CLUB_ID=theisland
BOOKING_FORM_URL=https://bookings.teemail.io
```

Booking URLs will be: `https://bookings.teemail.io/theisland/book`

### Multi-Club Setup

For multiple clubs, each club needs its own configuration:

**Club 1 - The Island:**
```bash
DATABASE_CLUB_ID=theisland
BOOKING_FORM_URL=https://bookings.teemail.io
FROM_NAME=The Island Golf Club
```

**Club 2 - Lahinch:**
```bash
DATABASE_CLUB_ID=lahinch
BOOKING_FORM_URL=https://bookings.teemail.io
FROM_NAME=Lahinch Golf Club
```

**Club 3 - Adare:**
```bash
DATABASE_CLUB_ID=adare
BOOKING_FORM_URL=https://bookings.teemail.io
FROM_NAME=Adare Manor Golf Club
```

## Routes

### Booking Form Display
```
GET /<club>/book
GET /book  # Backward compatibility - uses DATABASE_CLUB_ID
```

**Parameters:**
- `booking_id` - Unique booking identifier
- `date` - Booking date (YYYY-MM-DD)
- `time` - Tee time (HH:MM)
- `players` - Number of players
- `email` - Customer email

**Example:**
```
GET /theisland/book?booking_id=ISL-001&date=2026-01-15&time=10:00&players=4&email=john@example.com
```

### Booking Form Submission
```
POST /<club>/submit-booking-form
POST /submit-booking-form  # Backward compatibility - uses DATABASE_CLUB_ID
```

**Form Fields:**
- `booking_id` - Booking identifier
- `club_id` - Club identifier
- `date` - Booking date
- `tee_time` - Tee time
- `players` - Number of players
- `total` - Total cost
- `guest_email` - Customer email
- `lead_name` - Lead guest name (required)
- `caddie_requirements` - Caddie preferences
- `fb_requirements` - Food & beverage requirements
- `special_requests` - Special requests

**Response:**
```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_..."
}
```

## Deployment Strategies

### Strategy 1: Single Domain, Multiple Clubs

Use one domain for all clubs with path-based routing:

```
bookings.teemail.io/theisland/book
bookings.teemail.io/lahinch/book
bookings.teemail.io/adare/book
```

**Advantages:**
- Single deployment
- Shared SSL certificate
- Easy to manage
- Cost effective

**Configuration:**
```bash
BOOKING_FORM_URL=https://bookings.teemail.io
```

### Strategy 2: Multiple Domains

Use separate domains for each club:

```
book.theisland.ie/theisland/book
book.lahinch.ie/lahinch/book
book.adare.ie/adare/book
```

**Advantages:**
- Brand-specific URLs
- Better SEO
- White-label appearance

**Configuration:**
```bash
# For The Island
BOOKING_FORM_URL=https://book.theisland.ie

# For Lahinch
BOOKING_FORM_URL=https://book.lahinch.ie
```

### Strategy 3: Subdomain Routing

Use subdomains for each club:

```
theisland.bookings.teemail.io/book
lahinch.bookings.teemail.io/book
adare.bookings.teemail.io/book
```

**Advantages:**
- Clean URLs
- Single wildcard SSL cert
- Easy subdomain management

**DNS Configuration:**
```
*.bookings.teemail.io  CNAME  your-app.onrender.com
```

## Code Implementation

### Building Booking Links

The `build_booking_link()` function accepts a club parameter:

```python
# In your email template generation
booking_link = build_booking_link(
    date="2026-01-15",
    time="10:00",
    players=4,
    guest_email="customer@example.com",
    booking_id="ISL-001",
    club="theisland"  # Club identifier
)
# Returns: https://bookings.teemail.io/theisland/book?...
```

### Route Handlers

Routes accept club as a path parameter:

```python
@app.route('/<club>/book', methods=['GET'])
@app.route('/book', methods=['GET'])  # Backward compatibility
def book_redirect(club=None):
    club_id = club or DATABASE_CLUB_ID
    # ... display booking form
```

### Database Updates

Club ID is stored with every booking:

```python
# Stripe webhook handler
club_id = session['metadata'].get('club')

update_data = {
    'status': 'Confirmed',
    'club': club_id,  # Stored in database
    'lead_name': lead_name,
    # ... other fields
}
```

## Testing

### Test Single Club

```bash
# Visit booking form
curl "http://localhost:5000/theisland/book?booking_id=TEST-001&date=2026-01-15&time=10:00&players=4&email=test@example.com"
```

### Test Multiple Clubs

```bash
# The Island
curl "http://localhost:5000/theisland/book?..."

# Lahinch
curl "http://localhost:5000/lahinch/book?..."

# Adare
curl "http://localhost:5000/adare/book?..."
```

### Test Backward Compatibility

```bash
# Old URL format (no club in path)
curl "http://localhost:5000/book?booking_id=TEST-001&..."
# Falls back to DATABASE_CLUB_ID
```

## Migration Guide

### From Single Club to Multi-Club

1. **Update Environment Variables**
   ```bash
   # Before
   DATABASE_CLUB_ID=demo

   # After
   DATABASE_CLUB_ID=theisland
   ```

2. **Update Email Templates**

   No changes needed - the system automatically includes the club ID from `DATABASE_CLUB_ID` when generating booking links.

3. **Test Booking Flow**
   - Send test inquiry email
   - Click "Book Now" button
   - Verify URL contains club ID: `/theisland/book`
   - Complete test booking
   - Verify club stored in database

4. **Deploy Additional Clubs**

   Deploy separate instances with different `DATABASE_CLUB_ID` values, or use the same instance with path-based routing.

## Troubleshooting

### Booking Links Missing Club ID

**Problem:** Booking links look like `/book?...` instead of `/theisland/book?...`

**Solution:** Ensure `DATABASE_CLUB_ID` is set and `format_inquiry_email()` is being called with the club parameter.

### Wrong Club in Database

**Problem:** Bookings saved with wrong club ID

**Solution:** Check that:
1. Club is passed through Stripe metadata
2. Webhook extracts club from metadata
3. Database update includes club field

### 404 on Booking Form

**Problem:** `/theisland/book` returns 404

**Solution:**
1. Verify Flask routes are registered: `@app.route('/<club>/book')`
2. Check that `club` parameter is accepted in function
3. Restart Flask application

### Form Submission Fails

**Problem:** Form submits but returns error

**Solution:**
1. Check form action URL includes club: `action="/{{ club_id }}/submit-booking-form"`
2. Verify club_id hidden field is populated
3. Check that route accepts club parameter

## Best Practices

1. **Use Descriptive Club IDs**
   - Use lowercase, URL-friendly identifiers
   - Good: `theisland`, `lahinch`, `adare`
   - Bad: `The Island`, `club-1`, `id123`

2. **Consistent Club IDs**
   - Use the same club ID everywhere:
     - Environment variable: `DATABASE_CLUB_ID=theisland`
     - URL path: `/theisland/book`
     - Database: `club='theisland'`

3. **Database Indexing**
   - The `club` column is indexed for fast filtering
   - Dashboard queries use this index

4. **URL Validation**
   - Club IDs are extracted from URLs
   - No special validation needed (Flask handles routing)
   - Non-existent clubs fall back to `DATABASE_CLUB_ID`

## Security Considerations

1. **Club ID Validation**

   Club IDs come from URLs but are not user-controlled in the booking flow. They're set by the system when generating "Book Now" links.

2. **Database Access**

   Dashboard users only see bookings for their configured club (`DATABASE_CLUB_ID`).

3. **Stripe Metadata**

   Club ID is stored in Stripe metadata and verified on webhook callbacks.

## Examples

### Complete Booking Flow

1. **Customer sends inquiry email**
   ```
   From: customer@example.com
   To: theisland@bookings.teemail.io
   Subject: Golf booking for 4 players on January 15
   ```

2. **System generates response with booking links**
   ```html
   <a href="https://bookings.teemail.io/theisland/book?booking_id=ISL-001&date=2026-01-15&time=10:00&players=4&email=customer@example.com">
     Book Now
   </a>
   ```

3. **Customer clicks "Book Now"**
   - Redirects to: `https://bookings.teemail.io/theisland/book?...`
   - Form displays with The Island branding
   - Form action: `/theisland/submit-booking-form`

4. **Customer fills out form and clicks "Book and Pay"**
   - POST to `/theisland/submit-booking-form`
   - Stripe session created with `club='theisland'` in metadata
   - Redirect to Stripe checkout

5. **Customer completes payment**
   - Stripe webhook fires
   - System extracts `club='theisland'` from metadata
   - Booking saved to database with club ID
   - Dashboard shows booking for The Island

## Support

For issues or questions about multi-club setup:

1. Check logs for club ID values
2. Verify environment variables are set correctly
3. Test with sample booking URLs
4. Review database entries for club field
