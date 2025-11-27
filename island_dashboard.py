#!/usr/bin/env python3
"""
The Island Golf Club - Dashboard with Waitlist, Analytics, Marketing & Export Integration
=========================================================================================

Streamlit dashboard for managing bookings, waitlist, analytics, and marketing segmentation.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import requests
import json

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
PER_PLAYER_FEE = float(os.getenv("PER_PLAYER_FEE", "325.00"))

# Page configuration
st.set_page_config(
    page_title="The Island Golf Club - Dashboard",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #003B7C;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2D5F3F;
        margin-top: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #003B7C;
    }
    .success-badge {
        background-color: #dcfce7;
        color: #166534;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
    }
    .warning-badge {
        background-color: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# Database connection pool
db_pool = None


def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    try:
        if not DATABASE_URL:
            return False
        db_pool = SimpleConnectionPool(minconn=1, maxconn=5, dsn=DATABASE_URL)
        return True
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return False


def get_db_connection():
    """Get a connection from the pool"""
    if db_pool:
        return db_pool.getconn()
    return None


def release_db_connection(conn):
    """Release connection back to pool"""
    if db_pool and conn:
        db_pool.putconn(conn)


@st.cache_data(ttl=60)
def get_bookings():
    """Fetch all bookings from database"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM bookings ORDER BY created_at DESC
        """)
        bookings = cursor.fetchall()
        cursor.close()
        return [dict(b) for b in bookings]
    except Exception as e:
        st.error(f"Error fetching bookings: {e}")
        return []
    finally:
        if conn:
            release_db_connection(conn)


@st.cache_data(ttl=60)
def get_waitlist():
    """Fetch all waitlist requests from database"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM waitlist ORDER BY priority DESC, created_at ASC
        """)
        waitlist = cursor.fetchall()
        cursor.close()
        return [dict(w) for w in waitlist]
    except Exception as e:
        st.error(f"Error fetching waitlist: {e}")
        return []
    finally:
        if conn:
            release_db_connection(conn)


@st.cache_data(ttl=300)
def get_analytics_data():
    """Fetch analytics data from database"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {}

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Lead time analytics
        cursor.execute("""
            SELECT
                AVG(date - DATE(created_at)) as avg_lead_days,
                MIN(date - DATE(created_at)) as min_lead_days,
                MAX(date - DATE(created_at)) as max_lead_days
            FROM bookings
            WHERE date IS NOT NULL AND created_at IS NOT NULL AND date >= DATE(created_at)
        """)
        lead_times = cursor.fetchone()

        # Status distribution
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM bookings
            GROUP BY status
        """)
        status_dist = cursor.fetchall()

        # Revenue by month
        cursor.execute("""
            SELECT
                DATE_TRUNC('month', created_at) as month,
                SUM(CASE WHEN status = 'confirmed' THEN total ELSE 0 END) as revenue,
                COUNT(*) as bookings
            FROM bookings
            WHERE created_at >= NOW() - INTERVAL '6 months'
            GROUP BY month
            ORDER BY month
        """)
        monthly_revenue = cursor.fetchall()

        # Customer frequency
        cursor.execute("""
            SELECT
                CASE
                    WHEN COUNT(*) = 1 THEN 'One-time'
                    WHEN COUNT(*) BETWEEN 2 AND 3 THEN 'Occasional'
                    WHEN COUNT(*) BETWEEN 4 AND 6 THEN 'Regular'
                    ELSE 'Frequent'
                END as frequency,
                COUNT(DISTINCT guest_email) as customers
            FROM bookings
            GROUP BY guest_email
        """)

        cursor.execute("""
            SELECT frequency, SUM(customers) as total FROM (
                SELECT
                    CASE
                        WHEN cnt = 1 THEN 'One-time'
                        WHEN cnt BETWEEN 2 AND 3 THEN 'Occasional'
                        WHEN cnt BETWEEN 4 AND 6 THEN 'Regular'
                        ELSE 'Frequent'
                    END as frequency,
                    1 as customers
                FROM (SELECT guest_email, COUNT(*) as cnt FROM bookings GROUP BY guest_email) sub
            ) sub2
            GROUP BY frequency
        """)
        customer_freq = cursor.fetchall()

        cursor.close()

        return {
            'lead_times': dict(lead_times) if lead_times else {},
            'status_distribution': [dict(s) for s in status_dist],
            'monthly_revenue': [dict(m) for m in monthly_revenue],
            'customer_frequency': [dict(c) for c in customer_freq]
        }
    except Exception as e:
        st.error(f"Error fetching analytics: {e}")
        return {}
    finally:
        if conn:
            release_db_connection(conn)


@st.cache_data(ttl=300)
def get_marketing_segments():
    """Fetch marketing segments from database"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {}

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # High value customers
        cursor.execute("""
            SELECT guest_email, SUM(CASE WHEN status = 'confirmed' THEN total ELSE 0 END) as revenue,
                   COUNT(*) as bookings
            FROM bookings
            GROUP BY guest_email
            HAVING SUM(CASE WHEN status = 'confirmed' THEN total ELSE 0 END) >= 1000
            ORDER BY revenue DESC
            LIMIT 50
        """)
        high_value = cursor.fetchall()

        # Lapsed customers
        cursor.execute("""
            SELECT guest_email, MAX(created_at) as last_activity, COUNT(*) as past_bookings
            FROM bookings
            GROUP BY guest_email
            HAVING MAX(created_at) < NOW() - INTERVAL '90 days'
            ORDER BY last_activity DESC
            LIMIT 50
        """)
        lapsed = cursor.fetchall()

        # Frequent non-bookers
        cursor.execute("""
            SELECT guest_email, COUNT(*) as inquiries
            FROM bookings
            WHERE status != 'confirmed'
            GROUP BY guest_email
            HAVING COUNT(*) >= 2
            ORDER BY inquiries DESC
            LIMIT 50
        """)
        non_bookers = cursor.fetchall()

        cursor.close()

        return {
            'high_value': [dict(h) for h in high_value],
            'lapsed': [dict(l) for l in lapsed],
            'non_bookers': [dict(n) for n in non_bookers]
        }
    except Exception as e:
        st.error(f"Error fetching segments: {e}")
        return {}
    finally:
        if conn:
            release_db_connection(conn)


def render_bookings_page():
    """Render the bookings management page"""
    st.markdown('<h1 class="main-header">Bookings Management</h1>', unsafe_allow_html=True)

    bookings = get_bookings()

    if not bookings:
        st.info("No bookings found.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    total_bookings = len(bookings)
    confirmed = sum(1 for b in bookings if b.get('status') == 'confirmed')
    provisional = sum(1 for b in bookings if b.get('status') == 'provisional')
    total_revenue = sum(float(b.get('total', 0) or 0) for b in bookings if b.get('status') == 'confirmed')

    with col1:
        st.metric("Total Bookings", total_bookings)
    with col2:
        st.metric("Confirmed", confirmed)
    with col3:
        st.metric("Provisional", provisional)
    with col4:
        st.metric("Revenue", f"€{total_revenue:,.2f}")

    st.markdown("---")

    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "confirmed", "provisional", "cancelled"])
    with col2:
        date_from = st.date_input("From Date", datetime.now() - timedelta(days=30))
    with col3:
        date_to = st.date_input("To Date", datetime.now() + timedelta(days=30))

    # Filter bookings
    filtered_bookings = bookings
    if status_filter != "All":
        filtered_bookings = [b for b in filtered_bookings if b.get('status') == status_filter]

    # Display bookings table
    if filtered_bookings:
        df = pd.DataFrame(filtered_bookings)
        display_cols = ['booking_id', 'guest_email', 'date', 'tee_time', 'players', 'total', 'status', 'created_at']
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True
        )


def render_waitlist_page():
    """Render the waitlist management page"""
    st.markdown('<h1 class="main-header">Waitlist Management</h1>', unsafe_allow_html=True)

    # Add new waitlist request
    with st.expander("Add New Waitlist Request", expanded=False):
        with st.form("add_waitlist"):
            col1, col2 = st.columns(2)
            with col1:
                guest_email = st.text_input("Guest Email*")
                guest_name = st.text_input("Guest Name")
                requested_date = st.date_input("Requested Date*")
            with col2:
                players = st.number_input("Players*", min_value=1, max_value=20, value=4)
                preferred_time = st.time_input("Preferred Time")
                flexibility = st.selectbox("Flexibility", ["flexible", "strict", "very_flexible"])

            notes = st.text_area("Notes")
            priority = st.slider("Priority", 0, 10, 5)

            submitted = st.form_submit_button("Add to Waitlist")

            if submitted:
                if guest_email and requested_date and players:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            request_id = f"WL-{datetime.now().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"
                            cursor.execute("""
                                INSERT INTO waitlist (request_id, guest_email, guest_name, requested_date,
                                    preferred_time_start, players, flexibility, priority, notes)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (request_id, guest_email, guest_name, requested_date,
                                  preferred_time, players, flexibility, priority, notes))
                            conn.commit()
                            cursor.close()
                            st.success(f"Added to waitlist: {request_id}")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            release_db_connection(conn)
                else:
                    st.error("Please fill in all required fields")

    st.markdown("---")

    # Display waitlist
    waitlist = get_waitlist()

    if not waitlist:
        st.info("No waitlist requests found.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    pending = sum(1 for w in waitlist if w.get('status') == 'pending')
    notified = sum(1 for w in waitlist if w.get('status') == 'notified')
    converted = sum(1 for w in waitlist if w.get('status') == 'converted')
    expired = sum(1 for w in waitlist if w.get('status') == 'expired')

    with col1:
        st.metric("Pending", pending)
    with col2:
        st.metric("Notified", notified)
    with col3:
        st.metric("Converted", converted)
    with col4:
        st.metric("Expired", expired)

    st.markdown("---")

    # Filter by status
    status_filter = st.selectbox("Filter by Status", ["All", "pending", "notified", "converted", "expired", "cancelled"])

    filtered_waitlist = waitlist
    if status_filter != "All":
        filtered_waitlist = [w for w in filtered_waitlist if w.get('status') == status_filter]

    # Display waitlist
    for item in filtered_waitlist:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                st.write(f"**{item.get('request_id', 'N/A')}**")
                st.write(f"📧 {item.get('guest_email', 'N/A')}")

            with col2:
                st.write(f"📅 {item.get('requested_date', 'N/A')}")
                st.write(f"👥 {item.get('players', 'N/A')} players")

            with col3:
                status = item.get('status', 'pending')
                status_colors = {
                    'pending': '🟡',
                    'notified': '🔵',
                    'converted': '🟢',
                    'expired': '🔴',
                    'cancelled': '⚫'
                }
                st.write(f"{status_colors.get(status, '⚪')} {status.upper()}")
                st.write(f"Priority: {item.get('priority', 0)}")

            with col4:
                if item.get('status') == 'pending':
                    if st.button("Notify", key=f"notify_{item.get('request_id')}"):
                        st.info("Notification functionality - configure via API")
                    if st.button("Convert", key=f"convert_{item.get('request_id')}"):
                        st.info("Conversion functionality - configure via API")

            st.markdown("---")


def render_analytics_page():
    """Render the analytics page"""
    st.markdown('<h1 class="main-header">Enhanced Analytics</h1>', unsafe_allow_html=True)

    analytics = get_analytics_data()

    # Lead Time Analytics
    st.markdown('<h2 class="sub-header">Booking Lead Times</h2>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    lead_times = analytics.get('lead_times', {})

    with col1:
        avg_days = lead_times.get('avg_lead_days', 0)
        st.metric("Average Lead Time", f"{float(avg_days or 0):.1f} days")
    with col2:
        min_days = lead_times.get('min_lead_days', 0)
        st.metric("Minimum Lead Time", f"{int(min_days or 0)} days")
    with col3:
        max_days = lead_times.get('max_lead_days', 0)
        st.metric("Maximum Lead Time", f"{int(max_days or 0)} days")

    # Lead Time Distribution Chart
    bookings = get_bookings()
    if bookings:
        lead_times_list = []
        for b in bookings:
            if b.get('date') and b.get('created_at'):
                try:
                    booking_date = b['date'] if isinstance(b['date'], datetime) else datetime.strptime(str(b['date'])[:10], '%Y-%m-%d')
                    created_date = b['created_at'] if isinstance(b['created_at'], datetime) else datetime.strptime(str(b['created_at'])[:10], '%Y-%m-%d')
                    lead_days = (booking_date - created_date.replace(tzinfo=None) if hasattr(created_date, 'tzinfo') else booking_date - created_date).days
                    if lead_days >= 0:
                        lead_times_list.append(lead_days)
                except Exception:
                    pass

        if lead_times_list:
            fig = px.histogram(
                x=lead_times_list,
                nbins=20,
                title="Lead Time Distribution",
                labels={'x': 'Days in Advance', 'y': 'Number of Bookings'},
                color_discrete_sequence=['#003B7C']
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Status Distribution
    st.markdown('<h2 class="sub-header">Booking Status Distribution</h2>', unsafe_allow_html=True)

    status_dist = analytics.get('status_distribution', [])
    if status_dist:
        fig = px.pie(
            values=[s['count'] for s in status_dist],
            names=[s['status'] for s in status_dist],
            title="Bookings by Status",
            color_discrete_sequence=['#2D5F3F', '#D4AF37', '#B91C2E', '#003B7C']
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Monthly Revenue Trend
    st.markdown('<h2 class="sub-header">Monthly Revenue Trend</h2>', unsafe_allow_html=True)

    monthly_revenue = analytics.get('monthly_revenue', [])
    if monthly_revenue:
        df_monthly = pd.DataFrame(monthly_revenue)
        if 'month' in df_monthly.columns:
            df_monthly['month'] = pd.to_datetime(df_monthly['month'])
            fig = px.bar(
                df_monthly,
                x='month',
                y='revenue',
                title="Monthly Revenue",
                labels={'month': 'Month', 'revenue': 'Revenue (€)'},
                color_discrete_sequence=['#003B7C']
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Customer Frequency
    st.markdown('<h2 class="sub-header">Customer Inquiry Frequency</h2>', unsafe_allow_html=True)

    customer_freq = analytics.get('customer_frequency', [])
    if customer_freq:
        fig = px.bar(
            x=[c['frequency'] for c in customer_freq],
            y=[c['total'] for c in customer_freq],
            title="Customers by Inquiry Frequency",
            labels={'x': 'Frequency Category', 'y': 'Number of Customers'},
            color_discrete_sequence=['#2D5F3F']
        )
        st.plotly_chart(fig, use_container_width=True)


def render_marketing_page():
    """Render the marketing segmentation page"""
    st.markdown('<h1 class="main-header">Marketing Segmentation</h1>', unsafe_allow_html=True)

    segments = get_marketing_segments()

    # Segment tabs
    tab1, tab2, tab3 = st.tabs(["High Value Customers", "Lapsed Customers", "Frequent Non-Bookers"])

    with tab1:
        st.markdown('<h2 class="sub-header">High Value Customers (€1000+ Revenue)</h2>', unsafe_allow_html=True)
        st.markdown("*Customers with significant confirmed booking revenue - ideal for VIP programs and exclusive offers.*")

        high_value = segments.get('high_value', [])
        if high_value:
            st.metric("Segment Size", len(high_value))

            df = pd.DataFrame(high_value)
            df['revenue'] = df['revenue'].apply(lambda x: f"€{float(x):,.2f}" if x else "€0.00")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Export button
            if st.button("Export High Value Customers", key="export_high_value"):
                csv = pd.DataFrame(high_value).to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"high_value_customers_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
        else:
            st.info("No high value customers found.")

    with tab2:
        st.markdown('<h2 class="sub-header">Lapsed Customers (90+ Days Inactive)</h2>', unsafe_allow_html=True)
        st.markdown("*Previously active customers who haven't engaged in 90+ days - ideal for re-engagement campaigns.*")

        lapsed = segments.get('lapsed', [])
        if lapsed:
            st.metric("Segment Size", len(lapsed))

            df = pd.DataFrame(lapsed)
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("Export Lapsed Customers", key="export_lapsed"):
                csv = pd.DataFrame(lapsed).to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"lapsed_customers_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
        else:
            st.info("No lapsed customers found.")

    with tab3:
        st.markdown('<h2 class="sub-header">Frequent Non-Bookers (2+ Inquiries, No Confirmations)</h2>', unsafe_allow_html=True)
        st.markdown("*Customers who inquire frequently but rarely book - may need incentives or personal follow-up.*")

        non_bookers = segments.get('non_bookers', [])
        if non_bookers:
            st.metric("Segment Size", len(non_bookers))

            df = pd.DataFrame(non_bookers)
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("Export Non-Bookers", key="export_non_bookers"):
                csv = pd.DataFrame(non_bookers).to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"frequent_non_bookers_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )
        else:
            st.info("No frequent non-bookers found.")


def render_export_page():
    """Render the notify integration/export page"""
    st.markdown('<h1 class="main-header">Notify Platform Integration</h1>', unsafe_allow_html=True)

    st.markdown("""
    Export booking data in various formats for integration with external notification systems,
    CRM platforms, or marketing automation tools.
    """)

    # Export options
    st.markdown('<h2 class="sub-header">Export Bookings</h2>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Filter Options")
        status_filter = st.selectbox("Status", ["All", "confirmed", "provisional", "cancelled"], key="export_status")
        date_from = st.date_input("From Date", datetime.now() - timedelta(days=30), key="export_from")
        date_to = st.date_input("To Date", datetime.now(), key="export_to")

    with col2:
        st.markdown("### Export Format")
        export_format = st.selectbox("Format", ["JSON", "CSV"])

    # Get filtered bookings
    bookings = get_bookings()
    filtered = bookings

    if status_filter != "All":
        filtered = [b for b in filtered if b.get('status') == status_filter]

    st.markdown(f"**{len(filtered)} bookings** match your filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generate Export", type="primary"):
            if filtered:
                if export_format == "JSON":
                    # Convert datetime objects to strings
                    export_data = []
                    for b in filtered:
                        b_copy = dict(b)
                        for key, value in b_copy.items():
                            if isinstance(value, datetime):
                                b_copy[key] = value.isoformat()
                            elif hasattr(value, 'isoformat'):
                                b_copy[key] = str(value)
                        export_data.append(b_copy)

                    json_str = json.dumps({
                        'exported_at': datetime.now().isoformat(),
                        'count': len(export_data),
                        'data': export_data
                    }, indent=2, default=str)

                    st.download_button(
                        "Download JSON",
                        json_str,
                        f"bookings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        "application/json"
                    )
                else:  # CSV
                    df = pd.DataFrame(filtered)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"bookings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )
            else:
                st.warning("No bookings to export")

    st.markdown("---")

    # API Push configuration
    st.markdown('<h2 class="sub-header">API Push Configuration</h2>', unsafe_allow_html=True)

    st.markdown("""
    Configure webhooks to automatically push booking data to external systems.
    """)

    with st.expander("Configure API Push Endpoint"):
        webhook_url = st.text_input("Webhook URL", placeholder="https://your-system.com/webhook/bookings")
        auth_header = st.text_input("Authorization Header (optional)", placeholder="Bearer your-api-key")

        if st.button("Test Connection"):
            if webhook_url:
                st.info(f"Testing connection to: {webhook_url}")
                st.warning("Note: Configure this in your deployment environment for production use.")
            else:
                st.error("Please enter a webhook URL")

    st.markdown("---")

    # Export logs
    st.markdown('<h2 class="sub-header">Export History</h2>', unsafe_allow_html=True)

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM export_logs ORDER BY created_at DESC LIMIT 20")
            logs = cursor.fetchall()
            cursor.close()

            if logs:
                df = pd.DataFrame([dict(l) for l in logs])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No export history found.")
        except Exception as e:
            st.info("Export logs table not yet initialized.")
        finally:
            release_db_connection(conn)


def main():
    """Main application entry point"""
    # Initialize database
    init_db_pool()

    # Sidebar navigation
    st.sidebar.image("https://via.placeholder.com/200x80?text=The+Island+GC", width=200)
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        ["Bookings", "Waitlist", "Analytics", "Marketing Segmentation", "Notify Integration"],
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Stats")

    # Quick stats
    bookings = get_bookings()
    if bookings:
        today_bookings = sum(1 for b in bookings if b.get('date') and str(b['date'])[:10] == datetime.now().strftime('%Y-%m-%d'))
        st.sidebar.metric("Today's Bookings", today_bookings)

        total_revenue = sum(float(b.get('total', 0) or 0) for b in bookings if b.get('status') == 'confirmed')
        st.sidebar.metric("Total Revenue", f"€{total_revenue:,.0f}")

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")

    if st.sidebar.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Render selected page
    if page == "Bookings":
        render_bookings_page()
    elif page == "Waitlist":
        render_waitlist_page()
    elif page == "Analytics":
        render_analytics_page()
    elif page == "Marketing Segmentation":
        render_marketing_page()
    elif page == "Notify Integration":
        render_export_page()


if __name__ == "__main__":
    main()
