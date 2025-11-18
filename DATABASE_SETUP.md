# Database Setup and Troubleshooting

## Initial Database Setup

### 1. Apply the Schema

Connect to your PostgreSQL database and run the schema file:

```bash
psql $DATABASE_URL -f schema.sql
```

Or using Python:

```python
import psycopg2
import os

DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)

with open('schema.sql', 'r') as f:
    schema = f.read()

with conn.cursor() as cur:
    cur.execute(schema)

conn.commit()
conn.close()
```

### 2. Verify the Schema

```sql
\d bookings
```

Expected columns:
- `id` (VARCHAR, PRIMARY KEY)
- `name` (VARCHAR)
- `email` (VARCHAR, NOT NULL)
- `phone` (VARCHAR)
- `num_players` (INTEGER)
- `preferred_date` (VARCHAR)
- `preferred_time` (VARCHAR)
- `alternate_date` (VARCHAR)
- `special_requests` (TEXT)
- `status` (VARCHAR)
- `total_fee` (DECIMAL)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)
- `course_id` (VARCHAR)
- `internal_notes` (TEXT)
- `raw_email_data` (JSONB)

## Common Issues

### Issue: `column "name" of relation "bookings" does not exist`

**Cause**: The database schema is outdated or incomplete.

**Solution**: Run the schema.sql file to create/update the table structure.

### Issue: Database connection fails

**Cause**: DATABASE_URL environment variable not set or incorrect.

**Solution**:
1. Check that DATABASE_URL is set in your environment
2. Format should be: `postgresql://user:password@host:port/database`
3. For Render.com, use the Internal Database URL from the dashboard

## SendGrid Email Issues

### Issue: `HTTP Error 403: Forbidden`

**Possible causes and solutions**:

1. **API Key Issues**
   - Verify the SENDGRID_API_KEY environment variable is set correctly
   - Check that the API key has "Mail Send" permissions in SendGrid
   - Generate a new API key if needed: SendGrid Dashboard → Settings → API Keys

2. **Sender Verification**
   - SendGrid requires sender email verification
   - Go to: SendGrid Dashboard → Settings → Sender Authentication
   - Verify your FROM_EMAIL address (bookings@theislandgolfclub.ie)
   - Option A: Single Sender Verification (quick, for testing)
   - Option B: Domain Authentication (recommended for production)

3. **Domain Authentication** (Recommended)
   - Authenticate your domain (theislandgolfclub.ie) with SendGrid
   - Add the provided DNS records to your domain
   - This improves deliverability and removes SendGrid branding

4. **Account Status**
   - Check if your SendGrid account is in good standing
   - Free tier has limits (100 emails/day)
   - Verify account is not suspended

### Testing SendGrid Setup

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os

message = Mail(
    from_email='bookings@theislandgolfclub.ie',
    to_emails='your-test-email@example.com',
    subject='Test Email',
    html_content='<p>This is a test email from The Island Golf Club</p>'
)

try:
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    response = sg.send(message)
    print(f"Success! Status code: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
```

## Environment Variables Checklist

Ensure these are set in your environment (Render.com Dashboard → Environment):

- ✅ `DATABASE_URL` - PostgreSQL connection string
- ✅ `SENDGRID_API_KEY` - SendGrid API key with Mail Send permissions
- ✅ `FROM_EMAIL` - Verified sender email (default: bookings@theislandgolfclub.ie)
- ✅ `FROM_NAME` - Sender name (default: The Island Golf Club)
- ⚪ `PER_PLAYER_FEE` - Fee per player (default: 325.00)
- ⚪ `DEFAULT_COURSE_ID` - Course identifier (default: theisland)

## Monitoring

Check the application logs for:
- ✅ "Stored booking {id} in database" - successful DB write
- ✅ "Email sent to {email}: 200" - successful email send
- ❌ "Failed to store booking in database" - DB error
- ❌ "Failed to send email" - SendGrid error

## Support

For database issues, check:
- PostgreSQL logs
- Connection pool status
- Database user permissions

For email issues, check:
- SendGrid Activity Feed (Dashboard → Activity)
- Email event logs
- Sender verification status
