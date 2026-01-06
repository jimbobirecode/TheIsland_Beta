# Booking Form Custom Domain Configuration

This guide explains how to configure a custom domain for your booking form.

## Current Setup

The booking form is served at the `/book` endpoint of your Flask application. By default, it uses the main application URL.

## Configuration Options

### Option 1: Use Main Application Domain
If your booking form should be on the same domain as your main application, simply set:

```bash
BOOKING_APP_URL=https://your-main-domain.com
```

Example:
```bash
BOOKING_APP_URL=https://bookings.theisland.ie
```

This will make booking links: `https://bookings.theisland.ie/book?booking_id=...`

### Option 2: Use Separate Booking Form Domain
If you want the booking form on a different domain (e.g., for branding or load balancing), set:

```bash
BOOKING_APP_URL=https://main-app.com
BOOKING_FORM_URL=https://book.yourclub.com
```

Example:
```bash
BOOKING_APP_URL=https://theisland-email-bot.onrender.com
BOOKING_FORM_URL=https://book.theisland.ie
```

This will make:
- Booking links: `https://book.theisland.ie/book?booking_id=...`
- Success page: `https://theisland-email-bot.onrender.com/booking-success`
- Cancel page: `https://theisland-email-bot.onrender.com/booking-cancelled`

## How to Set Environment Variables

### On Render.com
1. Go to your service dashboard
2. Navigate to "Environment" tab
3. Click "Add Environment Variable"
4. Add `BOOKING_FORM_URL` with your custom domain
5. Click "Save Changes"
6. Your service will automatically redeploy

### On Railway.app
1. Go to your project
2. Click on your service
3. Navigate to "Variables" tab
4. Click "New Variable"
5. Add `BOOKING_FORM_URL` with your custom domain
6. Deploy

### Using .env file (Local Development)
Create or update `.env` file:
```bash
BOOKING_FORM_URL=https://book.yourclub.com
```

## Domain Setup (DNS Configuration)

### If using the same server
Set up a CNAME or A record pointing to your application:

**For CNAME (recommended):**
```
book.yourclub.com  CNAME  your-app.onrender.com
```

**For A Record:**
```
book.yourclub.com  A  [your-server-ip]
```

### If using a separate server
1. Deploy the Flask application to a separate server/service
2. Point your custom domain to that server
3. Ensure all routes (/book, /submit-booking-form, /booking-success, /booking-cancelled) are accessible

## SSL/HTTPS Configuration

Most hosting providers (Render, Railway, Vercel) automatically provide SSL certificates for custom domains. Make sure to:

1. Add your custom domain in the hosting platform
2. Wait for SSL certificate provisioning (usually 5-15 minutes)
3. Always use `https://` in your environment variables

## Testing Your Configuration

After setting up, test the flow:

1. **Generate a test booking link:**
   ```
   https://your-booking-domain.com/book?booking_id=TEST-001&date=2026-01-15&time=10:00&players=4&email=test@example.com
   ```

2. **Verify the form loads correctly**

3. **Test form submission** (it should redirect to Stripe)

4. **Complete a test payment** (use Stripe test cards)

5. **Verify redirect back** to success page

## Current Configuration

Based on your environment variables:
- Main App: `BOOKING_APP_URL` = {{BOOKING_APP_URL}}
- Booking Form: `BOOKING_FORM_URL` = {{BOOKING_FORM_URL}} (defaults to BOOKING_APP_URL if not set)
- Success URL: `STRIPE_SUCCESS_URL` = {{STRIPE_SUCCESS_URL}}
- Cancel URL: `STRIPE_CANCEL_URL` = {{STRIPE_CANCEL_URL}}

## Troubleshooting

### Booking links still using old domain
- Clear your application cache
- Restart your application server
- Check that environment variables are set correctly

### SSL Certificate errors
- Wait 10-15 minutes after adding domain
- Verify DNS propagation: `dig your-domain.com`
- Check hosting provider's SSL status

### Stripe redirect issues
- Ensure `STRIPE_SUCCESS_URL` and `STRIPE_CANCEL_URL` are accessible
- Verify these URLs in Stripe Dashboard → Settings → Redirect URLs
- Add your domains to Stripe's allowed redirect URLs list

## Example Configurations

### Single Domain Setup
```bash
BOOKING_APP_URL=https://bookings.theisland.ie
# BOOKING_FORM_URL not set (uses BOOKING_APP_URL)
STRIPE_SUCCESS_URL=https://bookings.theisland.ie/booking-success
STRIPE_CANCEL_URL=https://bookings.theisland.ie/booking-cancelled
```

### Multi-Domain Setup
```bash
BOOKING_APP_URL=https://admin.theisland.ie
BOOKING_FORM_URL=https://book.theisland.ie
STRIPE_SUCCESS_URL=https://book.theisland.ie/booking-success
STRIPE_CANCEL_URL=https://book.theisland.ie/booking-cancelled
```

### Custom Branding Setup
```bash
BOOKING_APP_URL=https://theisland-email-bot.onrender.com
BOOKING_FORM_URL=https://reserve.theisland.ie
STRIPE_SUCCESS_URL=https://reserve.theisland.ie/booking-success
STRIPE_CANCEL_URL=https://reserve.theisland.ie/booking-cancelled
```

## Support

If you encounter issues:
1. Check application logs for errors
2. Verify DNS settings using online DNS checkers
3. Test with `curl -I https://your-domain.com/book` to verify server response
4. Ensure your firewall/security groups allow HTTPS traffic (port 443)
