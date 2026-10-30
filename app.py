from pathlib import Path
from io import BytesIO, StringIO
import json
import csv
import os
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")
import psycopg
from psycopg.rows import dict_row
import re
import base64
import pandas as pd
import numpy as np
import streamlit as st
import time
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from auth import (init_auth_db, user_count, register_user, authenticate, list_users, list_audit_logs, admin_create_user, admin_update_user, admin_delete_user, transfer_primary_admin, change_own_password)
from psycopg_pool import ConnectionPool



# Apply the Green Teal palette to every Plotly chart in the dashboard.
pio.templates["shipiq_blue"] = pio.templates["plotly_dark"]
pio.templates["shipiq_blue"].layout.update(
    paper_bgcolor="#0B1220",
    plot_bgcolor="#121D2D",
    font=dict(family="DM Sans, sans-serif", color="#EDF7FF"),
    title=dict(font=dict(color="#EDF7FF")),
    xaxis=dict(gridcolor="#263B50", zerolinecolor="#263B50", linecolor="#355064"),
    yaxis=dict(gridcolor="#263B50", zerolinecolor="#263B50", linecolor="#355064"),
    colorway=["#35D0C5", "#60A5FA", "#818CF8", "#FBBF24", "#F472B6", "#34D399"]
)
px.defaults.template = "shipiq_blue"
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / 'data'
DATE_COL = 'manifested_date'
STATUS_COL = 'shipment_status'
BRAND_FILES = {'Freely':'freely_patterns.xlsx','Kotart':'kotart_patterns.xlsx','BigBearFarms':'bigbearfarms_patterns.xlsx'}

st.set_page_config(page_title='ShipIQ | Shipment Intelligence', page_icon='📦', layout='wide', initial_sidebar_state='expanded')

st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --shipiq-bg:#0B1220; --shipiq-surface:#121D2D; --shipiq-surface2:#19283A; --shipiq-line:#263B50; --shipiq-gold:#35D0C5; --shipiq-ivory:#EDF7FF; --shipiq-muted:#9AAFC2; }
/* ShipIQ dark-teal theme: keep Streamlit's sidebar and controls in the same visual system. */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #121D2D 0%, #0B1220 100%) !important;
    border-right: 1px solid #263B50;
}
[data-testid="stSidebar"] > div:first-child { background: transparent !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #C3D3E0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #EDF7FF !important; }
[data-testid="stSidebar"] hr { border-color: #263B50 !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: .35rem; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: #121D2D;
    border: 1px solid #263B50;
    border-radius: 10px;
    padding: .35rem .55rem;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: #19283A !important;
    border-color: #35D0C5 !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] [data-baseweb="datepicker"] {
    background-color: #121D2D !important;
    color: #EDF7FF !important;
    border-color: #355064 !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: #19283A !important;
    color: #EDF7FF !important;
}
[data-testid="stSidebar"] button {
    border-color: #355064 !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"] {
    background: #121D2D !important;
    border: 1px solid #263B50 !important;
}
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
/* Main canvas and all primary dashboard surfaces */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
section[data-testid="stMain"] {
    background: #0B1220 !important;
    color: #EDF7FF !important;
}
[data-testid="stMainBlockContainer"] { background: transparent !important; }
[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3,
[data-testid="stMain"] p,
[data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] {
    color: #EDF7FF;
}
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #121D2D, #19283A);
    border: 1px solid #263B50;
    border-radius: 14px;
    padding: 14px 16px;
}
[data-testid="stMetricLabel"] p { color: #9AAFC2 !important; }
[data-testid="stMetricValue"] { color: #EDF7FF !important; }
[data-testid="stMetricDelta"] { color: #35D0C5 !important; }
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #263B50 !important;
}
[data-testid="stMain"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-baseweb="input"] > div,
[data-testid="stMain"] input,
[data-testid="stMain"] textarea {
    background-color: #121D2D !important;
    color: #EDF7FF !important;
    border-color: #355064 !important;
}
[data-testid="stMain"] [data-testid="stAlert"] {
    background: #121D2D !important;
    border: 1px solid #263B50 !important;
}
[data-testid="stMain"] button[kind="primary"] {
    background: #19283A !important;
    border: 1px solid #35D0C5 !important;
    color: #EDF7FF !important;
}
[data-testid="stMain"] button[kind="secondary"] {
    background: #121D2D !important;
    border-color: #355064 !important;
    color: #EDF7FF !important;
}
[data-testid="stMain"] [data-testid="stDataFrame"],
[data-testid="stMain"] [data-testid="stTable"] {
    border: 1px solid #263B50;
    border-radius: 10px;
    overflow: hidden;
}
.stApp { background:radial-gradient(ellipse at 12% 0%,rgba(53,208,197,.10),transparent 35%),#0B1220; color:var(--shipiq-ivory); }

.shipiq-kicker { display:block; width:100%; font-size:.82rem; letter-spacing:.16em; text-transform:uppercase; color:#174454 !important; -webkit-text-fill-color:#174454 !important; font-weight:900; line-height:1.7; opacity:1 !important; visibility:visible !important; text-shadow:none; margin-bottom:.5rem; overflow:visible; }
.shipiq-title { font-family:'Manrope',sans-serif; font-size:2.35rem; font-weight:800; letter-spacing:-.055em; line-height:1.08; color:var(--shipiq-ivory); }
.shipiq-sub { color:var(--shipiq-muted); font-size:1rem; margin-top:.55rem; line-height:1.65; }


</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_excel(path, brand):
    df = pd.read_excel(path)
    df['brand'] = brand
    return df

def normalize_status(v):
    """Normalize source statuses while distinguishing completed RTO from an RTO in progress."""
    if pd.isna(v) or not str(v).strip():
        return 'Unknown'
    s = re.sub(r'\s+', ' ', str(v).strip().lower())

    # Explicit final outcomes first. An RTO workflow is not a completed return until
    # the source status confirms the shipment was returned/delivered back.
    if any(x in s for x in ['cancel', 'voided']):
        return 'Cancelled'
    if any(x in s for x in ['lost', 'damage', 'destroy']):
        return 'Lost/Damaged'
    if any(x in s for x in ['undeliver', 'not delivered', 'delivery failed', 'failed delivery',
                            'failed', 'exception', 'attempt failed', 'non-delivery']):
        return 'Failed/Undelivered'
    if any(x in s for x in ['rto delivered', 'returned to origin', 'return to origin',
                            'return-to-origin delivered', 'returned']):
        return 'RTO'

    # RTO initiation, transit, or delivery attempts remain in progress unless the
    # source explicitly confirms a completed return.
    if 'rto' in s and any(x in s for x in ['transit', 'out for delivery', 'requested',
                                           'initiated', 'in process', 'processing', 'pending']):
        return 'In Transit/Attempting'
    if any(x in s for x in ['out for delivery', 'delivery attempted', 'attempting delivery',
                            'transit', 'shipped', 'picked', 'ndr', 'reached',
                            'in warehouse', 'in hub', 'pickup complete', 'picked up']):
        return 'In Transit/Attempting'
    if any(x in s for x in ['manifest', 'pickup pending', 'ready to ship', 'label',
                            'booked', 'order placed']):
        return 'Manifested/Pending'
    if 'deliver' in s or s in {'complete', 'completed', 'success', 'successful'}:
        return 'Delivered'
    return str(v).strip().title()

def data_quality_summary(df):
    """Return transparent data-quality checks; never silently discard source rows."""
    if df.empty:
        return {
            'Rows loaded': 0, 'Rows with invalid/missing manifested date': 0,
            'Rows with missing shipment status': 0, 'Rows with missing courier': 0,
            'Rows with missing destination state': 0, 'Rows with missing shipment ID': 0,
            'Duplicate shipment-ID rows': 0, 'Unknown/unmapped status rows': 0,
        }
    duplicate_rows = 0
    missing_ids = int(len(df))
    if 'shipment_id' in df.columns:
        ids = df['shipment_id'].astype('string').str.strip()
        valid_ids = ids.notna() & ids.ne('')
        missing_ids = int((~valid_ids).sum())
        duplicate_rows = int(ids[valid_ids].duplicated(keep=False).sum())
    known = {'Delivered', 'RTO', 'Cancelled', 'Lost/Damaged', 'Failed/Undelivered',
             'Manifested/Pending', 'In Transit/Attempting', 'Unknown'}
    return {
        'Rows loaded': int(len(df)),
        'Rows with invalid/missing manifested date': int(pd.to_datetime(df.get(DATE_COL, pd.Series(index=df.index, dtype='object')), errors='coerce').isna().sum()),
        'Rows with missing shipment status': int(df[STATUS_COL].isna().sum()) if STATUS_COL in df.columns else int(len(df)),
        'Rows with missing courier': int(df['courier_name'].isna().sum() + df['courier_name'].astype('string').str.strip().eq('').sum()) if 'courier_name' in df.columns else int(len(df)),
        'Rows with missing destination state': int(df['drop_location_state'].isna().sum() + df['drop_location_state'].astype('string').str.strip().eq('').sum()) if 'drop_location_state' in df.columns else int(len(df)),
        'Rows with missing shipment ID': missing_ids,
        'Duplicate shipment-ID rows': duplicate_rows,
        'Unknown/unmapped status rows': int((~df.get('normalized_status', pd.Series('Unknown', index=df.index)).isin(known)).sum()),
    }

def clean_df(df, brand):
    df = df.copy()
    df['brand'] = brand
    for c in ['manifested_date','invoice_date','latest_status_date','pickup_date','first_attempt_date','delivery_rto_date','edd','pdd','rto_initiation_date']:
        if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
    for c in ['shipment_status','courier_name','drop_location_state','drop_location_city','payment_type','shipment_type']:
        if c in df.columns: df[c] = df[c].astype('string').str.strip()
    if STATUS_COL not in df.columns: df[STATUS_COL] = 'Unknown'
    df['normalized_status'] = df[STATUS_COL].map(normalize_status)
    if 'courier_name' not in df.columns: df['courier_name'] = 'Unknown'
    df['courier_name'] = df['courier_name'].fillna('Unknown').replace('', 'Unknown')
    if 'drop_location_state' not in df.columns: df['drop_location_state'] = 'Unknown'
    df['drop_location_state'] = df['drop_location_state'].fillna('Unknown').replace('', 'Unknown')
    if DATE_COL not in df.columns: df[DATE_COL] = pd.NaT
    df['manifest_date'] = pd.to_datetime(df[DATE_COL], errors='coerce').dt.date
    df['is_delivered'] = df['normalized_status'].eq('Delivered')
    df['is_rto'] = df['normalized_status'].eq('RTO')
    df['is_cancelled'] = df['normalized_status'].eq('Cancelled')
    df['is_final'] = df['normalized_status'].isin(['Delivered','RTO','Cancelled','Lost/Damaged','Failed/Undelivered'])
    df['is_on_time'] = False
    if 'edd' in df.columns and 'latest_status_date' in df.columns:
        df['is_on_time'] = df['is_delivered'] & df['latest_status_date'].notna() & df['edd'].notna() & (df['latest_status_date'].dt.normalize() <= df['edd'].dt.normalize())
    return df

def load_defaults():
    parts=[]
    for brand, fname in BRAND_FILES.items():
        path=DATA_DIR/fname
        if path.exists():
            try: parts.append(clean_df(load_excel(str(path), brand), brand))
            except Exception as e: st.warning(f'Could not load {fname}: {e}')
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()

# Supabase PostgreSQL persistence. Set DATABASE_URL in the environment / Streamlit secrets.
# DB_PATH remains as a compatibility argument for existing auth helper signatures;
# PostgreSQL connection details are read only from DATABASE_URL.
DB_PATH = APP_DIR / 'shipiq_data.sqlite3'  # retained for compatibility; not used for database I/O


@st.cache_resource
def _get_db_pool(database_url):
    return ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=5,
        timeout=15,
        kwargs={"row_factory": dict_row},
        open=True,
    )

def _db_connect():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        try:
            database_url = st.secrets.get("DATABASE_URL")
        except Exception:
            database_url = None

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it in your environment or Streamlit secrets."
        )

    return _get_db_pool(database_url).connection()

def _init_database(conn):
    """Ensure shipment persistence tables/indexes exist in PostgreSQL."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            brand TEXT,
            manifested_date TEXT,
            shipment_id TEXT,
            payload_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipiq_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)


def save_dataset(dataset):
    """Replace the persisted shipment snapshot atomically in PostgreSQL."""
    records_json = dataset.to_json(orient='records', date_format='iso', date_unit='ms')
    records = json.loads(records_json) if records_json else []
    rows = []
    for record in records:
        brand = record.get('brand')
        manifested = record.get(DATE_COL)
        shipment_id = record.get('shipment_id')
        rows.append((
            None if brand is None else str(brand),
            None if manifested is None else str(manifested)[:10],
            None if shipment_id is None else str(shipment_id),
            json.dumps(record, ensure_ascii=False, separators=(',', ':'))
        ))
    with _db_connect() as conn:
        _init_database(conn)
        conn.execute('DELETE FROM shipments')
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    'INSERT INTO shipments (brand, manifested_date, shipment_id, payload_json) VALUES (%s, %s, %s, %s)',
                    rows
                )
        conn.execute(
            "INSERT INTO shipiq_metadata (key, value) VALUES ('schema_version', '2') "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value"
        )
    # Invalidate cached reads after a successful database write.
    st.cache_data.clear()


@st.cache_data(show_spinner=False, ttl=300)
def load_persisted_dataset():
    """Load the complete shipment snapshot. Used only in Data Management."""
    with _db_connect() as conn:
        _init_database(conn)
        rows = conn.execute('SELECT payload_json FROM shipments ORDER BY id').fetchall()
    if not rows:
        return None
    records = [json.loads(row['payload_json']) for row in rows]
    stored = pd.DataFrame(records)
    if stored.empty or 'brand' not in stored.columns:
        return stored
    parts = []
    for brand, group in stored.groupby('brand', dropna=False, sort=False):
        parts.append(clean_df(group, str(brand)))
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=300)
def load_brand_names():
    """Fetch only distinct brand names, never the full shipment payload."""
    with _db_connect() as conn:
        _init_database(conn)
        rows = conn.execute(
            "SELECT DISTINCT brand FROM shipments WHERE brand IS NOT NULL AND BTRIM(brand) <> '' ORDER BY brand"
        ).fetchall()
    names = [str(row['brand']) for row in rows]
    return names if names else sorted(BRAND_FILES.keys())


@st.cache_data(show_spinner=False, ttl=1800)
def load_persisted_brand(brand):
    """Load one brand efficiently using PostgreSQL COPY, then clean/cache the result.

    COPY streams the selected payload column through PostgreSQL's bulk-transfer
    protocol instead of returning thousands of individual result rows.
    """
    records = []
    with _db_connect() as conn:
        _init_database(conn)
        # COPY supports query parameters less directly than SELECT, so use a safe
        # parameterized query to retrieve the brand's internal ID values first.
        # The actual payload transfer remains a parameterized SELECT below if the
        # brand name contains characters requiring SQL escaping.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS row_count FROM shipments WHERE brand = %s",
                (brand,),
            )
            # The connection pool uses psycopg's dict_row factory, so rows
            # must be accessed by column name rather than numeric position.
            row_count = cur.fetchone()["row_count"]

            if row_count:
                # Quote the brand as a SQL literal using PostgreSQL's own
                # quote_literal function, avoiding manual SQL string escaping.
                cur.execute("SELECT quote_literal(%s) AS brand_literal", (brand,))
                brand_literal = cur.fetchone()["brand_literal"]
                copy_sql = (
                    "COPY (SELECT payload_json FROM shipments WHERE brand = "
                    + brand_literal
                    + " ORDER BY id) TO STDOUT WITH (FORMAT CSV)"
                )
                chunks = []
                with cur.copy(copy_sql) as copy:
                    while True:
                        chunk = copy.read()
                        if not chunk:
                            break
                        chunks.append(chunk)
                csv_text = b"".join(chunks).decode("utf-8")
                for csv_row in csv.reader(StringIO(csv_text)):
                    if csv_row:
                        records.append(json.loads(csv_row[0]))

    if records:
        return clean_df(pd.DataFrame(records), brand)

    # If the database has not been initialized yet, fall back to that brand's bundled file.
    filename = BRAND_FILES.get(brand)
    path = DATA_DIR / filename if filename else None
    if path is not None and path.exists():
        return clean_df(load_excel(str(path), brand), brand)
    return pd.DataFrame()

def rate(num, den): return (100*num/den) if den else 0.0

def metrics(df):
    total = len(df)
    delivered = int(df['is_delivered'].sum())
    rto = int(df['is_rto'].sum())
    cancelled = int(df['is_cancelled'].sum())
    final = int(df['is_final'].sum())
    known_pending = {'Manifested/Pending', 'In Transit/Attempting'}
    pending = int(df['normalized_status'].isin(known_pending).sum())
    recognized = {'Delivered', 'RTO', 'Cancelled', 'Lost/Damaged', 'Failed/Undelivered',
                  'Manifested/Pending', 'In Transit/Attempting'}
    unknown = int((~df['normalized_status'].isin(recognized)).sum())
    # Delivery/RTO rates use only shipments with a completed delivery or completed RTO.
    # Cancelled, pending, failed, and unknown outcomes are excluded from this rate denominator.
    completed_outcomes = delivered + rto
    return {
        'Shipments': total, 'Delivered': delivered,
        'Delivery rate': rate(delivered, completed_outcomes), 'RTO': rto,
        'RTO rate': rate(rto, completed_outcomes), 'Cancelled': cancelled,
        'Cancellation rate': rate(cancelled, final), 'Finalized': final,
        'Pending / in progress': pending, 'Unknown / unmapped status': unknown,
    }


def kpi_row(df, previous_df=None):
    m=metrics(df)
    previous = metrics(previous_df) if previous_df is not None and not previous_df.empty else None
    cols=st.columns(6)
    definitions=[
        ('Manifested', 'Shipments', 'count'),
        ('Delivered', 'Delivered', 'count'),
        ('RTO Delivered', 'RTO', 'count'),
        ('Cancelled', 'Cancelled', 'count'),
        ('Delivery rate*', 'Delivery rate', 'rate'),
        ('RTO rate*', 'RTO rate', 'rate'),
    ]
    for col,(label,key,kind) in zip(cols,definitions):
        value = m[key]
        display = f"{value:,.2f}%" if kind == 'rate' else f"{value:,}"
        delta = None
        if previous is not None:
            prev_value = previous[key]
            if kind == 'rate':
                delta = f"{value - prev_value:+.2f} pp vs prev day"
            elif prev_value:
                delta = f"{(value - prev_value) / prev_value * 100:+.1f}% vs prev day"
            elif value:
                delta = "New vs prev day"
            else:
                delta = "0.0% vs prev day"
        col.metric(label, display, delta=delta, delta_color="inverse" if key in ('RTO', 'Cancelled', 'RTO rate') else "normal")
    if previous_df is None or previous_df.empty:
        st.caption('Day-over-day comparison is unavailable because no shipments were found for the previous calendar day.')
    st.caption('* Delivery and RTO rates use completed deliveries + completed RTOs as the denominator. Day-over-day changes compare with the previous calendar day.')

    # Operational KPIs: attempt count and date-based turnaround times.
    st.markdown('#### Delivery operations')
    attempt_col = next((c for c in [
        'delivery_attempts', 'delivery_attempt_count', 'attempt_count',
        'no_of_attempts', 'number_of_attempts', 'attempts', 'delivery_attempt'
    ] if c in df.columns), None)
    if attempt_col is None:
        attempt_series = pd.Series(dtype='float64')
        attempt_avg = None
        high_attempts = None
    else:
        attempt_series = pd.to_numeric(df[attempt_col], errors='coerce')
        attempt_series = attempt_series[attempt_series >= 0]
        attempt_avg = float(attempt_series.mean()) if not attempt_series.empty else None
        high_attempts = int((attempt_series > 2).sum())

    manifested = pd.to_datetime(df.get('manifested_date', pd.Series(pd.NaT, index=df.index)), errors='coerce')
    pickup = pd.to_datetime(df.get('pickup_date', pd.Series(pd.NaT, index=df.index)), errors='coerce')
    delivery = pd.to_datetime(df.get('delivery_rto_date', pd.Series(pd.NaT, index=df.index)), errors='coerce')
    manifest_pickup = (pickup.dt.normalize() - manifested.dt.normalize()).dt.total_seconds() / 86400
    manifest_pickup = manifest_pickup[manifested.notna() & pickup.notna() & manifest_pickup.ge(0)]
    delivered_mask = df.get('is_delivered', pd.Series(False, index=df.index)).fillna(False).astype(bool)
    pickup_delivery = (delivery.dt.normalize() - pickup.dt.normalize()).dt.total_seconds() / 86400
    pickup_delivery = pickup_delivery[delivered_mask & pickup.notna() & delivery.notna() & pickup_delivery.ge(0)]

    attention_display = None
    op1, op2, op3 = st.columns(3)
    with op1:
        attempts_display = f'{attempt_avg:.2f}' if attempt_avg is not None else 'N/A'
        st.metric('Avg. delivery attempts', attempts_display,
                  help=(f'{high_attempts:,} shipments required more than 2 attempts.' if high_attempts is not None else
                        'No recognized delivery-attempt count column exists in this dataset.'))
        if high_attempts is not None:
            st.caption(f'⚠️ {high_attempts:,} shipments with >2 attempts')
            if high_attempts:
                attention = df.loc[attempt_series.index[attempt_series > 2]].copy()
                attention['_attempt_count'] = pd.to_numeric(attention[attempt_col], errors='coerce')
                attention = attention.sort_values('_attempt_count', ascending=False)
                preferred_cols = [
                    'shipment_id', 'brand', 'courier_name', STATUS_COL,
                    'manifested_date', 'pickup_date', 'delivery_rto_date',
                    'drop_location_city', 'drop_location_state'
                ]
                display_cols = [c for c in preferred_cols if c in attention.columns]
                # Ensure the attempt count is visible even when source naming varies.
                attention = attention[display_cols + ['_attempt_count']].rename(
                    columns={'_attempt_count': 'delivery_attempts'}
                )
                attention_display = attention
            elif attempt_avg is not None:
                st.caption('No shipments exceeded 2 recorded attempts in the selected data.')
    with op2:
        mp_display = f'{manifest_pickup.mean():.2f} days' if not manifest_pickup.empty else 'N/A'
        st.metric('Manifest → Pickup', mp_display,
                  help=f'Average across {len(manifest_pickup):,} shipments with valid, non-negative dates.')
    with op3:
        pd_display = f'{pickup_delivery.mean():.2f} days' if not pickup_delivery.empty else 'N/A'
        st.metric('Pickup → Delivery', pd_display,
                  help=f'Average delivered-shipment turnaround across {len(pickup_delivery):,} shipments with valid, non-negative dates.')

    # Render outside the three KPI columns so the attention table uses the full dashboard width.
    if attention_display is not None:
        st.markdown('##### ⚠️ Shipments requiring attention')
        st.caption('Shipments with more than 2 recorded delivery attempts, sorted from highest to lowest.')
        st.dataframe(attention_display, use_container_width=True, hide_index=True)

def rate_table(df, by):
    if df.empty: return pd.DataFrame()
    # Count source rows, not non-null shipment IDs, so missing IDs cannot silently lower shipment totals.
    g=df.groupby(by, dropna=False).agg(shipments=('normalized_status','size'), delivered=('is_delivered','sum'), rto=('is_rto','sum'), cancelled=('is_cancelled','sum'), finalized=('is_final','sum')).reset_index()
    g['delivery_rate_%']=np.where(g.finalized>0,100*g.delivered/g.finalized,0).round(1)
    g['rto_rate_%']=np.where(g.finalized>0,100*g.rto/g.finalized,0).round(1)
    g['cancellation_rate_%']=np.where(g.finalized>0,100*g.cancelled/g.finalized,0).round(1)
    return g.sort_values(['delivery_rate_%','shipments'],ascending=[False,False])

def pdf_report(df, title, filters_text):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph('ShipIQ | Shipment Intelligence', styles['Title']))
    story.append(Paragraph(title, styles['Heading2']))
    story.append(Paragraph(filters_text, styles['Normal']))
    story.append(Spacer(1, 12))
    m = metrics(df)
    summary = [['Metric', 'Value'], ['Total shipments', f"{m['Shipments']:,}"], ['Delivered', f"{m['Delivered']:,}"], ['Delivery rate (finalized shipments)', f"{m['Delivery rate']:.1f}%"], ['RTO', f"{m['RTO']:,}"], ['RTO rate (finalized shipments)', f"{m['RTO rate']:.1f}%"], ['Cancelled', f"{m['Cancelled']:,}"], ['Cancellation rate (finalized shipments)', f"{m['Cancellation rate']:.1f}%"], ['Pending / in progress', f"{m['Pending / in progress']:,}"], ['Unknown / unmapped status', f"{m['Unknown / unmapped status']:,}"]]
    t = Table(summary, colWidths=[270, 150], repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17243b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.35,colors.lightgrey),('PADDING',(0,0),(-1,-1),7)]))
    story.append(t)
    story.append(Spacer(1, 14))

    def add_report_table(heading, headers, rows, widths=None, font_size=7):
        story.append(Paragraph(heading, styles['Heading3']))
        if not rows:
            story.append(Paragraph('No data available for this section in the selected filters.', styles['Normal']))
            story.append(Spacer(1, 8))
            return
        table_rows = [headers] + rows
        table = Table(table_rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17243b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),font_size),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),4)]))
        story.append(table)
        story.append(Spacer(1, 12))

    # Brand-wise analysis
    if 'brand' in df.columns:
        b = rate_table(df, 'brand')
        rows = [[str(r['brand'])[:28], int(r.shipments), int(r.delivered), f"{r['delivery_rate_%']:.1f}%", int(r.rto), f"{r['rto_rate_%']:.1f}%", int(r.cancelled)] for _, r in b.iterrows()]
        add_report_table('Brand-wise Analysis', ['Brand','Shipments','Delivered','Delivery %','RTO','RTO %','Cancelled'], rows, [120,58,58,62,45,52,55], 7)

    # State-wise analysis, using the same filtered shipment data as the report KPIs.
    if 'drop_location_state' in df.columns:
        state_summary = rate_table(df, 'drop_location_state')
        state_rows = [[str(r['drop_location_state'])[:32], int(r.shipments), int(r.delivered), f"{r['delivery_rate_%']:.1f}%", int(r.rto), f"{r['rto_rate_%']:.1f}%", int(r.cancelled), f"{r['cancellation_rate_%']:.1f}%"] for _, r in state_summary.iterrows()]
        add_report_table('State-wise Analysis', ['Destination State','Shipments','Delivered','Delivery %','RTO','RTO %','Cancelled','Cancel %'], state_rows, [125,55,55,60,40,48,50,55], 6.5)

    # Courier-wise analysis
    if 'courier_name' in df.columns:
        c = rate_table(df, 'courier_name')
        courier_rows = [[str(r['courier_name'])[:32], int(r.shipments), int(r.delivered), f"{r['delivery_rate_%']:.1f}%", int(r.rto), f"{r['rto_rate_%']:.1f}%", int(r.cancelled)] for _, r in c.head(40).iterrows()]
        add_report_table('Courier-wise Analysis (top 40)', ['Courier','Shipments','Delivered','Delivery %','RTO','RTO %','Cancelled'], courier_rows, [140,58,58,62,45,52,55], 7)

    # Rule-based AI recommendations, aligned with the dashboard's recommendation thresholds.
    story.append(Paragraph('AI Recommendations', styles['Heading3']))
    if df.empty:
        story.append(Paragraph('No recommendations are available because no shipments match the selected filters.', styles['Normal']))
    else:
        brand_summary = rate_table(df, 'brand') if 'brand' in df.columns else pd.DataFrame()
        recommendation_count = 0
        for _, brand_row in brand_summary.sort_values('shipments', ascending=False).iterrows():
            brand = str(brand_row['brand'])
            brand_data = df[df['brand'].astype(str) == brand]
            bm = metrics(brand_data)
            recs = []
            if bm['Shipments'] < 10:
                recs.append(f"Small sample size: only {bm['Shipments']} shipments; treat rates as directional and consider a longer date range.")
            if bm['Delivery rate'] < 90 and bm['Finalized'] >= 10:
                recs.append(f"Improve delivery success: delivery rate is {bm['Delivery rate']:.1f}%. Review failed delivery reasons, address quality, delivery attempts, and courier performance.")
            elif bm['Delivery rate'] >= 97 and bm['Finalized'] >= 10:
                recs.append(f"Maintain delivery performance: delivery rate is {bm['Delivery rate']:.1f}%. Identify and preserve the operating practices behind this result.")
            if bm['RTO rate'] >= 10 and bm['Finalized'] >= 10:
                recs.append(f"Reduce RTO: rate is {bm['RTO rate']:.1f}%. Investigate COD orders, failed attempts, customer availability, and high-RTO destination areas.")
            if bm['Cancelled'] > 0:
                recs.append(f"Investigate cancellations: {bm['Cancelled']:,} cancellations; cancellation rate is {bm['Cancellation rate']:.1f}% of finalized outcomes.")
            if bm['Pending / in progress'] > 0:
                recs.append(f"Follow up on pending/in-progress shipments: {bm['Pending / in progress']:,} shipments need aging and tracking review.")
            if bm['Unknown / unmapped status'] > 0:
                recs.append(f"Improve status mapping: {bm['Unknown / unmapped status']:,} rows have unknown/unmapped statuses; normalize them before relying on comparisons.")
            courier_summary = rate_table(brand_data, 'courier_name') if 'courier_name' in brand_data.columns else pd.DataFrame()
            eligible = courier_summary[courier_summary['shipments'] >= 5].copy() if not courier_summary.empty else pd.DataFrame()
            if len(eligible) >= 2:
                best = eligible.sort_values(['delivery_rate_%','shipments'], ascending=[False,False]).iloc[0]
                worst = eligible.sort_values(['delivery_rate_%','shipments'], ascending=[True,False]).iloc[0]
                if float(best['delivery_rate_%']) - float(worst['delivery_rate_%']) >= 10:
                    recs.append(f"Review courier allocation: {best['courier_name']} is at {best['delivery_rate_%']:.1f}% delivery versus {worst['courier_name']} at {worst['delivery_rate_%']:.1f}%; compare serviceability and shipment mix before reallocating.")
            if not recs:
                recs.append('Keep monitoring: no major threshold-based risk stood out in the selected data. Continue monitoring delivery, RTO, cancellation, and pending-shipment KPIs.')
            story.append(Paragraph(brand, styles['Heading4']))
            for rec in recs:
                story.append(Paragraph('&bull; ' + rec.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), styles['Normal']))
                story.append(Spacer(1, 3))
                recommendation_count += 1
        if recommendation_count == 0:
            story.append(Paragraph('No brand-level recommendations could be generated from the selected data.', styles['Normal']))
    story.append(Spacer(1, 10))
    story.append(Paragraph('Methodology: delivery, RTO and cancellation rates use finalized shipments as the denominator. Pending/in-progress shipments are excluded from these rate denominators. Shipment status is normalized from the source status field; validate status mapping and recommendations against operational context before making decisions.', styles['Italic']))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

# Authentication gate: auth tables are stored in Supabase PostgreSQL.
init_auth_db(DB_PATH)

def render_auth_screen():
    st.markdown('<div class="shipiq-kicker">PATTERNS · LOGISTICS INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="shipiq-title">ShipIQ</div>', unsafe_allow_html=True)
    st.markdown('<div class="shipiq-sub">Sign in to your shipment intelligence workspace.</div>', unsafe_allow_html=True)
    st.write("")
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])
    with login_tab:
        with st.form("shipiq_login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if login_submit:
            user, error = authenticate(DB_PATH, login_email, login_password)
            if user:
                st.session_state.auth_user = user
                st.rerun()
            else:
                st.error(error or "Unable to sign in.")
    with register_tab:
        if user_count(DB_PATH) == 0:
            st.info("The first account created becomes the primary Admin account.")
        else:
            st.info("Self-registration creates a Viewer account. An Admin can change your role later.")
        with st.form("shipiq_register_form"):
            reg_name = st.text_input("Full name", key="reg_name")
            reg_email = st.text_input("Email address", key="reg_email")
            reg_password = st.text_input("Password (minimum 10 characters)", type="password", key="reg_password")
            reg_confirm = st.text_input("Confirm password", type="password", key="reg_confirm")
            reg_submit = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if reg_submit:
            if reg_password != reg_confirm:
                st.error("Passwords do not match.")
            else:
                ok, message, user = register_user(DB_PATH, reg_name, reg_email, reg_password)
                if ok:
                    st.success("Account created successfully. Please sign in using your email address and password.")
                    st.info("Your account is ready. Open the Sign in tab to log in.")
                else:
                    st.error(message)

if "auth_user" not in st.session_state:
    render_auth_screen()
    st.stop()

# Refresh role/status from PostgreSQL on every rerun so deactivated users lose access promptly.
_current_user = next((u for u in list_users(DB_PATH) if int(u["id"]) == int(st.session_state.auth_user.get("id", -1))), None)
if not _current_user or not _current_user["is_active"]:
    st.session_state.pop("auth_user", None)
    st.warning("Your account is inactive or no longer exists. Please sign in again.")
    render_auth_screen()
    st.stop()
st.session_state.auth_user.update(_current_user)
AUTH_USER = st.session_state.auth_user
ROLE = AUTH_USER["role"]

if 'custom_brands' not in st.session_state:
    st.session_state.custom_brands = []

with st.sidebar:
    st.markdown('## 📦 ShipIQ')
    st.caption('Shipment Intelligence Control Tower')
    nav_pages = ['Executive Overview','Brand-wise Analysis','AI Recommendation','State-wise Analysis','Courier-wise Analysis']
    if ROLE in ('Admin','Analyst'):
        nav_pages.extend(['Data Management','Reports'])
    if ROLE == 'Admin':
        nav_pages.append('User Management')
    st.divider()
    page = st.radio('NAVIGATION', nav_pages, label_visibility='collapsed')
    st.divider()

    analytics_pages = {
        'Executive Overview', 'Brand-wise Analysis', 'AI Recommendation',
        'State-wise Analysis', 'Courier-wise Analysis', 'Reports'
    }
    selected_brand = None
    start_d = end_d = None
    chosen_brands = []

    if page == 'Data Management':
        # Full data is deliberately loaded only when a user opens Data Management,
        # because upload/delete/reset operations need the complete snapshot.
        with st.spinner('Loading saved datasets for data management...'):
            persisted_dataset = load_persisted_dataset()
            st.session_state.dataset = persisted_dataset if persisted_dataset is not None else load_defaults()
        all_data = st.session_state.dataset.copy()
    elif page in analytics_pages:
        brand_options = load_brand_names()
        selected_brand = st.selectbox(
            'Select brand to analyse',
            options=['Select a brand', 'All Brands'] + brand_options,
            index=0,
            key='shipiq_selected_brand',
            help='Analytics load only after you explicitly select a brand.'
        )
        if selected_brand == 'Select a brand':
            st.session_state.dataset = pd.DataFrame()
            all_data = pd.DataFrame()
            st.info('Select a brand to load its shipment analytics.')
        elif selected_brand == 'All Brands':
            with st.spinner('Loading shipment data for all brands...'):
                persisted_dataset = load_persisted_dataset()
                st.session_state.dataset = persisted_dataset if persisted_dataset is not None else load_defaults()
            all_data = st.session_state.dataset.copy()
            chosen_brands = sorted(all_data['brand'].dropna().astype(str).unique().tolist()) if not all_data.empty and 'brand' in all_data.columns else []
        else:
            with st.spinner(f'Loading {selected_brand} shipment data...'):
                st.session_state.dataset = load_persisted_brand(selected_brand)
            all_data = st.session_state.dataset.copy()
            chosen_brands = [selected_brand]

        # Show the same date filters for a single brand and for All Brands.
        if selected_brand != 'Select a brand' and not all_data.empty:
            dates = pd.to_datetime(all_data[DATE_COL], errors='coerce').dropna()
            if not dates.empty:
                min_d, max_d = dates.min().date(), dates.max().date()
                mode = st.radio(
                    'Date filter',
                    ['Date range', 'Single date'],
                    horizontal=False,
                    key='analytics_date_filter_mode'
                )
                if mode == 'Single date':
                    chosen = st.date_input(
                        'Manifested date',
                        value=max_d,
                        min_value=min_d,
                        max_value=max_d,
                        key='analytics_single_date'
                    )
                    start_d = end_d = chosen
                else:
                    selected = st.date_input(
                        'Manifested date range',
                        value=(min_d, max_d),
                        min_value=min_d,
                        max_value=max_d,
                        key='analytics_date_range'
                    )
                    if isinstance(selected, tuple) and len(selected) == 2:
                        start_d, end_d = selected
                    else:
                        start_d = end_d = selected
                st.caption('Dates are based on manifested_date.')
        elif selected_brand != 'Select a brand':
            st.warning(f'No shipment records were found for {selected_brand}.')
    else:
        # User Management does not need to load shipment payloads.
        st.session_state.dataset = pd.DataFrame()
        all_data = pd.DataFrame()

    st.divider()
    st.markdown(f"**{AUTH_USER['full_name']}**")
    st.caption(AUTH_USER['email'] + " · " + ROLE + (" · Primary Admin" if AUTH_USER["is_primary_admin"] else ""))
    if st.button("Sign out", key="shipiq_sign_out", use_container_width=True):
        st.session_state.pop("auth_user", None)
        st.rerun()
    with st.expander("Change my password"):
        with st.form("shipiq_change_password"):
            current_pw = st.text_input("Current password", type="password", key="current_pw")
            new_pw = st.text_input("New password (10+ characters)", type="password", key="new_pw")
            confirm_pw = st.text_input("Confirm new password", type="password", key="confirm_new_pw")
            change_pw_submit = st.form_submit_button("Update password")
        if change_pw_submit:
            if new_pw != confirm_pw:
                st.error("New passwords do not match.")
            else:
                ok, message = change_own_password(DB_PATH, AUTH_USER["id"], current_pw, new_pw)
                (st.success if ok else st.error)(message)

# Filter by manifested date and brand, shared across all analytics and exports.
def apply_filters(data):
    d=data.copy()
    if not d.empty:
        if start_d is not None and end_d is not None:
            md=pd.to_datetime(d[DATE_COL],errors='coerce').dt.date
            d=d[(md>=start_d)&(md<=end_d)]
        if chosen_brands: d=d[d['brand'].astype(str).isin(chosen_brands)]
        else: d=d.iloc[0:0]
    return d

filtered=apply_filters(st.session_state.dataset)

# For single-date views, compare against the previous calendar day using the same brand selection.
previous_day_data = pd.DataFrame()
if start_d is not None and end_d is not None and start_d == end_d:
    previous_day = start_d - pd.Timedelta(days=1)
    previous_day_data = st.session_state.dataset.copy()
    if not previous_day_data.empty:
        previous_manifested = pd.to_datetime(previous_day_data[DATE_COL], errors='coerce').dt.date
        previous_day_data = previous_day_data[previous_manifested == previous_day]
        if chosen_brands:
            previous_day_data = previous_day_data[previous_day_data['brand'].astype(str).isin(chosen_brands)]
        else:
            previous_day_data = previous_day_data.iloc[0:0]

filter_text=f"Manifested date: {start_d or 'All'} to {end_d or 'All'} | Brand: {selected_brand if selected_brand and selected_brand != 'Select a brand' else 'None'}"

st.markdown('<div class="shipiq-kicker">PATTERNS · LOGISTICS INTELLIGENCE</div>',unsafe_allow_html=True)
st.markdown('<div class="shipiq-title">ShipIQ</div>',unsafe_allow_html=True)
st.markdown('<div class="shipiq-sub">A clearer view of shipment health, courier performance, and delivery outcomes.</div>',unsafe_allow_html=True)
st.write('')

if page == 'User Management':
    if ROLE != 'Admin':
        st.error("Admin permission required.")
        st.stop()
    st.subheader("User Management")
    st.caption("Create accounts, manage roles and access, transfer primary ownership, and review the audit trail.")
    users = list_users(DB_PATH)
    if users:
        display_users = pd.DataFrame(users).rename(columns={
            "id":"User ID","full_name":"Name","email":"Email","role":"Role",
            "is_active":"Active","is_primary_admin":"Primary Admin",
            "created_at":"Created","updated_at":"Updated","last_login":"Last login"
        })
        st.dataframe(display_users, use_container_width=True, hide_index=True)
    st.divider()
    create_col, edit_col = st.columns(2)
    with create_col:
        st.markdown("#### Create user")
        with st.form("admin_create_user_form"):
            new_name = st.text_input("Full name", key="admin_new_name")
            new_email = st.text_input("Email", key="admin_new_email")
            new_user_password = st.text_input("Temporary password (10+ characters)", type="password", key="admin_new_password")
            new_role = st.selectbox("Role", ["Viewer","Analyst","Admin"], key="admin_new_role")
            create_submit = st.form_submit_button("Create user", type="primary")
        if create_submit:
            ok, message = admin_create_user(DB_PATH, AUTH_USER["id"], new_name, new_email, new_user_password, new_role)
            (st.success if ok else st.error)(message)
            if ok:
                st.rerun()
    with edit_col:
        st.markdown("#### Update user")
        editable_users = [u for u in users if int(u["id"]) != int(AUTH_USER["id"])]
        if editable_users:
            selected_id = st.selectbox("Select user", [int(u["id"]) for u in editable_users],
                format_func=lambda uid: next((u["full_name"] + " · " + u["email"] for u in editable_users if int(u["id"]) == uid), str(uid)),
                key="admin_edit_user_id")
            selected_user = next(u for u in editable_users if int(u["id"]) == int(selected_id))
            with st.form("admin_edit_user_form"):
                edit_name = st.text_input("Name", value=selected_user["full_name"], key="admin_edit_name")
                edit_role = st.selectbox("Role", ["Admin","Analyst","Viewer"], index=["Admin","Analyst","Viewer"].index(selected_user["role"]), key="admin_edit_role")
                edit_active = st.checkbox("Account active", value=bool(selected_user["is_active"]), key="admin_edit_active")
                edit_submit = st.form_submit_button("Save user changes", type="primary")
            if edit_submit:
                ok, message = admin_update_user(DB_PATH, AUTH_USER["id"], selected_id, role=edit_role, is_active=edit_active, full_name=edit_name)
                (st.success if ok else st.error)(message)
                if ok:
                    st.rerun()
            delete_confirm = st.checkbox("I confirm I want to permanently delete this user", key="admin_delete_confirm")
            if st.button("Delete selected user", type="secondary", disabled=not delete_confirm, key="admin_delete_user_btn"):
                ok, message = admin_delete_user(DB_PATH, AUTH_USER["id"], selected_id)
                (st.success if ok else st.error)(message)
                if ok:
                    st.rerun()
        else:
            st.info("Create another user to manage a different account.")
    st.divider()
    st.markdown("#### Transfer primary Admin ownership")
    st.caption("The recipient must already be an active Admin. Your Admin role will remain unchanged.")
    active_admins = [u for u in users if u["role"] == "Admin" and u["is_active"] and int(u["id"]) != int(AUTH_USER["id"])]
    if active_admins:
        with st.form("transfer_primary_admin_form"):
            transfer_target = st.selectbox("New primary Admin", [int(u["id"]) for u in active_admins],
                format_func=lambda uid: next((u["full_name"] + " · " + u["email"] for u in active_admins if int(u["id"]) == uid), str(uid)))
            transfer_password = st.text_input("Confirm with your password", type="password", key="transfer_admin_password")
            transfer_confirm = st.checkbox("I understand this changes primary ownership", key="transfer_admin_confirm")
            transfer_submit = st.form_submit_button("Transfer ownership", disabled=False)
        if transfer_submit:
            if not transfer_confirm:
                st.error("Confirm the ownership transfer before continuing.")
            else:
                ok, message = transfer_primary_admin(DB_PATH, AUTH_USER["id"], transfer_target, transfer_password)
                (st.success if ok else st.error)(message)
                if ok:
                    st.rerun()
    else:
        st.info("Create or promote another active Admin before transferring ownership.")
    st.divider()
    st.markdown("#### Recent audit log")
    audit = list_audit_logs(DB_PATH, 100)
    if audit:
        st.dataframe(pd.DataFrame(audit), use_container_width=True, hide_index=True)
    else:
        st.info("No audit events yet.")

elif page == 'Data Management' and ROLE not in ('Admin','Analyst'):
    st.error("Your role is read-only. Data management requires Analyst or Admin access.")
    st.stop()
elif page == 'Reports' and ROLE not in ('Admin','Analyst'):
    st.error("Report exports require Analyst or Admin access.")
    st.stop()
elif page=='Executive Overview':
    st.subheader('Executive Overview')
    st.caption(filter_text)
    if selected_brand == 'Select a brand': st.info('Welcome to ShipIQ. Select a brand from the sidebar to load its analytics.')
    elif filtered.empty: st.info('No shipments match the selected brand and date filters.')
    else:
        kpi_row(filtered, previous_day_data if start_d is not None and end_d is not None and start_d == end_d else None)
        if start_d is not None and end_d is not None and start_d == end_d:
            st.caption(f"Comparing {start_d.strftime('%d %b %Y')} with {(start_d - pd.Timedelta(days=1)).strftime('%d %b %Y')}.")
        c1,c2=st.columns([1.5,1])
        with c1:
            daily=filtered.dropna(subset=[DATE_COL]).assign(manifest_day=lambda x:pd.to_datetime(x[DATE_COL]).dt.date).groupby('manifest_day').size().reset_index(name='shipments')
            st.plotly_chart(px.line(daily,x='manifest_day',y='shipments',markers=True,title='Daily manifested shipments',labels={'manifest_day':'Manifested date','shipments':'Shipments'}),use_container_width=True)
        with c2:
            statuses=filtered['normalized_status'].value_counts().rename_axis('status').reset_index(name='shipments')
            st.plotly_chart(px.pie(statuses,names='status',values='shipments',hole=.58,title='Shipment status mix'),use_container_width=True)
        st.subheader('Brand performance snapshot')
        st.dataframe(rate_table(filtered,'brand'),use_container_width=True,hide_index=True)
        st.subheader('Executive signals')
        m=metrics(filtered)
        signals=[]
        if m['Shipments']:
            signals.append(f"**{m['Pending / in progress']:,} shipments** are classified as pending/in progress. Outcome rates exclude these shipments until a final status is recorded.")
            if m['Unknown / unmapped status']:
                signals.append(f"**{m['Unknown / unmapped status']:,} shipments** have unknown or unmapped statuses; review the source-status mapping before interpreting the dashboard.")
            cr=rate_table(filtered,'courier_name')
            eligible=cr[cr['shipments']>=10]
            if not eligible.empty:
                best=eligible.sort_values(['delivery_rate_%','shipments'],ascending=[False,False]).iloc[0]
                signals.append(f"Among couriers with at least 10 shipments, **{best['courier_name']}** has the highest observed finalized-shipment delivery rate ({best['delivery_rate_%']:.1f}%). This is a descriptive ranking, not proof of causation.")
            if 'tat_breached' in filtered.columns:
                breached=pd.to_numeric(filtered['tat_breached'],errors='coerce').eq(1).sum()
                signals.append(f"**{breached:,} shipments** are flagged tat_breached=1 in the source data; confirm the source system's flag semantics before treating it as a service-level breach count.")
        for s in signals: st.markdown('- '+s)

elif page=='Brand-wise Analysis':
    st.subheader('Brand-wise Analysis'); st.caption(filter_text)
    if selected_brand == 'Select a brand': st.info('Select a brand from the sidebar to load its analytics.')
    elif filtered.empty: st.info('No data for the selected filters.')
    else:
        for brand in sorted(filtered['brand'].unique()):
            d=filtered[filtered.brand==brand]
            with st.expander(f"{brand} · {len(d):,} shipments",expanded=True):
                kpi_row(d)
                c1,c2=st.columns(2)
                daily=d.dropna(subset=[DATE_COL]).assign(manifest_day=lambda x:pd.to_datetime(x[DATE_COL]).dt.date).groupby('manifest_day').size().reset_index(name='shipments')
                with c1: st.plotly_chart(px.bar(daily,x='manifest_day',y='shipments',title=f'{brand}: daily manifests',labels={'manifest_day':'Date','shipments':'Shipments'}),use_container_width=True)
                with c2:
                    st.plotly_chart(px.bar(rate_table(d,'courier_name').head(12),x='courier_name',y='delivery_rate_%',title=f'{brand}: courier delivery rate',labels={'courier_name':'Courier','delivery_rate_%':'Delivery rate (%)'}),use_container_width=True)
                st.dataframe(rate_table(d,'courier_name'),use_container_width=True,hide_index=True)


elif page=='AI Recommendation':
    st.subheader('AI Recommendation')
    st.caption('Rule-based business recommendations generated from shipment KPIs for the selected manifested dates and brands. These are data-driven heuristics, not an external generative-AI model.')
    st.caption(filter_text)
    if selected_brand == 'Select a brand':
        st.info('Select a brand from the sidebar to generate recommendations.')
    elif filtered.empty:
        st.info('No shipments match the selected brand and dates. Adjust the date filter to generate recommendations.')
    else:
        brand_summary = rate_table(filtered, 'brand')
        st.markdown('Recommendations are generated separately for each brand using shipment volume, delivery rate, RTO rate, cancellations, pending shipments, and courier performance.')
        for _, row in brand_summary.sort_values('shipments', ascending=False).iterrows():
            brand = str(row['brand'])
            bd = filtered[filtered['brand'].astype(str) == brand].copy()
            bm = metrics(bd)
            with st.container(border=True):
                st.markdown(f"### {brand}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric('Shipments', f"{bm['Shipments']:,}")
                m2.metric('Delivery rate', f"{bm['Delivery rate']:.2f}%")
                m3.metric('RTO rate', f"{bm['RTO rate']:.2f}%")
                m4.metric('Cancelled', f"{bm['Cancelled']:,}")
                recommendations = []
                if bm['Shipments'] < 10:
                    recommendations.append(('ℹ️', 'Small sample size', f"Only {bm['Shipments']} shipments are in this selection. Treat rate changes as directional and review a longer date range before making operational changes."))
                if bm['Delivery rate'] < 90 and bm['Finalized'] >= 10:
                    recommendations.append(('🔴', 'Improve delivery success', f"Delivery rate is {bm['Delivery rate']:.2f}%. Review failed delivery reasons, address quality, delivery attempts, and courier performance for this period."))
                elif bm['Delivery rate'] >= 97 and bm['Finalized'] >= 10:
                    recommendations.append(('🟢', 'Maintain delivery performance', f"Delivery rate is strong at {bm['Delivery rate']:.2f}%. Identify the couriers and destination areas contributing to this result and maintain those operating practices."))
                if bm['RTO rate'] >= 10 and bm['Finalized'] >= 10:
                    recommendations.append(('🔴', 'Reduce return-to-origin shipments', f"RTO rate is {bm['RTO rate']:.2f}%. Investigate COD orders, failed delivery attempts, customer unavailability, and high-RTO pin codes before changing shipping rules."))
                if bm['Cancelled'] > 0:
                    cancel_rate = bm['Cancellation rate']
                    recommendations.append(('🟠', 'Investigate cancellations', f"{bm['Cancelled']} shipments were cancelled in the selected period (cancellation rate {cancel_rate:.2f}% of finalized outcomes). Check cancellation reasons, order confirmation, and dispatch timing."))
                if bm['Pending / in progress'] > 0:
                    recommendations.append(('🟡', 'Follow up on in-progress shipments', f"{bm['Pending / in progress']} shipments are pending/in progress. Review aging and latest tracking updates; prioritize shipments approaching or exceeding promised delivery time."))
                if bm['Unknown / unmapped status'] > 0:
                    recommendations.append(('🟡', 'Clean up shipment status mapping', f"{bm['Unknown / unmapped status']} rows have unknown or unmapped statuses. Normalize source statuses before relying on KPI comparisons."))
                couriers = rate_table(bd, 'courier_name')
                eligible = couriers[couriers['shipments'] >= 5].copy()
                if len(eligible) >= 2:
                    best = eligible.sort_values(['delivery_rate_%','shipments'], ascending=[False,False]).iloc[0]
                    worst = eligible.sort_values(['delivery_rate_%','shipments'], ascending=[True,False]).iloc[0]
                    if float(best['delivery_rate_%']) - float(worst['delivery_rate_%']) >= 10:
                        recommendations.append(('🔵', 'Review courier allocation', f"{best['courier_name']} has the highest observed delivery rate ({best['delivery_rate_%']:.1f}%) among couriers with at least 5 shipments, while {worst['courier_name']} is at {worst['delivery_rate_%']:.1f}%. Compare serviceability, shipment mix, and volumes before reallocating shipments."))
                if not recommendations:
                    recommendations.append(('🟢', 'Keep monitoring current performance', 'No major threshold-based risk stood out for this selection. Continue monitoring delivery, RTO, cancellation, and pending-shipment KPIs as more data arrives.'))
                for icon, title, detail in recommendations:
                    st.markdown(f"**{icon} {title}**")
                    st.write(detail)
                if not couriers.empty:
                    st.markdown('**Courier performance for this brand and period**')
                    st.dataframe(couriers[['courier_name','shipments','delivered','delivery_rate_%','rto','rto_rate_%','cancelled']], use_container_width=True, hide_index=True)
        st.caption('Interpretation note: rates are calculated using the app’s finalized-shipment denominator. Recommendations are descriptive and should be validated against shipment reasons, service levels, and operational context before acting.')

elif page=='State-wise Analysis':
    st.subheader('State-wise Analysis'); st.caption(filter_text)
    if selected_brand == 'Select a brand': st.info('Select a brand from the sidebar to load its analytics.')
    elif filtered.empty: st.info('No data for the selected filters.')
    else:
        st.caption('Courier rankings are based on finalized shipments. Low-volume comparisons can be volatile; use shipment counts alongside rates.')
        state=rate_table(filtered,'drop_location_state')
        st.plotly_chart(px.bar(state.head(25),x='drop_location_state',y='delivery_rate_%',hover_data=['shipments','delivered','rto','cancelled','rto_rate_%'],title='Delivery rate by destination state (top 25 by rate)',labels={'drop_location_state':'Destination state','delivery_rate_%':'Delivery rate (%)'}),use_container_width=True)
        st.dataframe(state,use_container_width=True,hide_index=True)
        st.subheader('Best-performing courier by state')
        min_n=st.slider('Minimum shipments per courier/state',1,50,5)
        sc=rate_table(filtered,['drop_location_state','courier_name'])
        sc=sc[sc['shipments']>=min_n].sort_values(['drop_location_state','delivery_rate_%','shipments'],ascending=[True,False,False])
        if not sc.empty:
            best=sc.drop_duplicates('drop_location_state',keep='first')
            st.dataframe(best[['drop_location_state','courier_name','shipments','delivered','delivery_rate_%','rto_rate_%','cancellation_rate_%']],use_container_width=True,hide_index=True)
        else: st.info('No state/courier groups meet the selected minimum shipment count.')
        st.subheader('Courier comparison within a state')
        states=sorted(filtered['drop_location_state'].dropna().astype(str).unique())
        chosen_state=st.selectbox('Choose destination state',states)
        st.dataframe(rate_table(filtered[filtered.drop_location_state.astype(str)==chosen_state],'courier_name'),use_container_width=True,hide_index=True)

elif page=='Courier-wise Analysis':
    st.subheader('Courier-wise Analysis'); st.caption(filter_text)
    if selected_brand == 'Select a brand': st.info('Select a brand from the sidebar to load its analytics.')
    elif filtered.empty: st.info('No data for the selected filters.')
    else:
        c=rate_table(filtered,'courier_name')
        min_n=st.slider('Minimum shipments for ranking',1,100,10)
        ranked=c[c.shipments>=min_n].sort_values(['delivery_rate_%','shipments'],ascending=[False,False])
        st.plotly_chart(px.bar(ranked.head(20),x='courier_name',y='delivery_rate_%',hover_data=['shipments','delivered','rto','cancelled','rto_rate_%'],title='Courier delivery rate (minimum-volume filter)',labels={'courier_name':'Courier','delivery_rate_%':'Delivery rate (%)'}),use_container_width=True)
        st.dataframe(ranked,use_container_width=True,hide_index=True)
        st.subheader('Courier performance by brand')
        cb=rate_table(filtered,['brand','courier_name'])
        st.dataframe(cb,use_container_width=True,hide_index=True)
        st.caption('Rate denominator: finalized shipments only (Delivered + RTO + Cancelled + Lost/Damaged + Failed/Undelivered). Pending shipments are excluded. Status normalization is heuristic and should be validated.')

elif page=='Data Management':
    st.subheader('Data Management')
    st.markdown('Upload shipment files, choose a single dataset date or a date range, and assign the data to an existing brand or create a new brand. Uploaded data is saved to Supabase PostgreSQL and persists across browser refreshes and app restarts.')

    existing_brands = sorted(st.session_state.dataset['brand'].dropna().astype(str).unique().tolist()) if not st.session_state.dataset.empty else sorted(BRAND_FILES.keys())
    add_new_option = '➕ Add new brand'
    brand_options = existing_brands + [add_new_option]

    # Keep these controls outside a form so selecting "Add new brand" reruns the
    # page immediately and reveals the name field before the user submits.
    up=st.file_uploader('Choose shipment dataset',type=['xlsx','xls','csv'],key='dataset_upload')
    date_mode=st.radio('Dataset date selection',['Single date','Date range'],horizontal=True,key='dataset_date_mode',
                       help='Use Single date for one daily export. Use Date range when the uploaded file contains manifested_date values across multiple days.')
    if date_mode == 'Single date':
        dataset_date=st.date_input('Dataset date',value=pd.Timestamp.today().date(),key='dataset_date_input',
                                   help='This date will be applied to every row in the uploaded daily batch.')
        range_start = range_end = None
    else:
        range_start, range_end = st.date_input('Dataset date range',value=(pd.Timestamp.today().date().replace(day=1),pd.Timestamp.today().date()),
                                               key='dataset_date_range_input',
                                               help='The uploaded file must contain manifested_date. Only rows within this inclusive date range will be added.')
        dataset_date = None
    brand_choice=st.selectbox('Brand',options=brand_options,index=0,key='dataset_brand_choice')
    new_brand_name = ''
    if brand_choice == add_new_option:
        new_brand_name = st.text_input('New brand name',placeholder='e.g. NewBrand',key='new_dataset_brand_name')
        st.caption('Enter the name of the new brand, then validate and add the dataset.')

    if st.button('Validate and add dataset',type='primary',key='validate_add_dataset'):
        resolved_brand = new_brand_name.strip() if brand_choice == add_new_option else brand_choice
        if up is None:
            st.error('Choose a shipment dataset first.')
        elif not resolved_brand:
            st.error('Enter a name for the new brand.')
        elif date_mode == 'Date range' and (range_start is None or range_end is None):
            st.error('Choose both the start and end dates.')
        elif date_mode == 'Date range' and range_start > range_end:
            st.error('The start date must be on or before the end date.')
        else:
            try:
                # Streamlit UploadedFile supports seek; reset before reading.
                up.seek(0)
                new=pd.read_csv(up) if up.name.lower().endswith('.csv') else pd.read_excel(up)
                if new.empty:
                    st.error('The uploaded file has no rows.')
                elif STATUS_COL not in new.columns:
                    st.error(f"Required column '{STATUS_COL}' was not found.")
                elif date_mode == 'Date range' and DATE_COL not in new.columns:
                    st.error(f"Date range upload requires a '{DATE_COL}' column containing each shipment's manifested date. Use Single date for a daily export without that column.")
                else:
                    if date_mode == 'Single date':
                        # A daily export represents one chosen day; stamp every row with it.
                        new[DATE_COL] = pd.Timestamp(dataset_date)
                        batch_dates = {dataset_date}
                    else:
                        parsed_dates = pd.to_datetime(new[DATE_COL], errors='coerce')
                        row_days = parsed_dates.dt.date
                        original_rows = len(new)
                        in_range = row_days.notna() & row_days.ge(range_start) & row_days.le(range_end)
                        new = new.loc[in_range].copy()
                        new[DATE_COL] = parsed_dates.loc[in_range]
                        if new.empty:
                            st.error(f"No rows have a valid manifested_date between {range_start.strftime('%d/%m/%Y')} and {range_end.strftime('%d/%m/%Y')}. Nothing was added.")
                            st.stop()
                        excluded_rows = original_rows - len(new)
                        batch_dates = set(pd.to_datetime(new[DATE_COL], errors='coerce').dt.date.dropna().tolist())
                    new=clean_df(new,resolved_brand)
                    old=st.session_state.dataset
                    # Replace only the uploaded brand's batch dates, keeping that brand's
                    # historical records for all dates outside this upload's date/date range.
                    if not old.empty and 'brand' in old.columns:
                        old_dates = pd.to_datetime(old[DATE_COL], errors='coerce').dt.date if DATE_COL in old.columns else pd.Series(None, index=old.index)
                        same_brand = old['brand'].astype(str).str.casefold().eq(resolved_brand.casefold())
                        if date_mode == 'Single date':
                            dates_to_replace = old_dates.eq(dataset_date)
                        else:
                            dates_to_replace = old_dates.ge(range_start) & old_dates.le(range_end)
                        old = old.loc[~(same_brand & dates_to_replace)]
                    st.session_state.dataset=pd.concat([old,new],ignore_index=True,sort=False)
                    save_dataset(st.session_state.dataset)
                    if date_mode == 'Single date':
                        date_description = dataset_date.strftime('%d/%m/%Y')
                    else:
                        date_description = f"{range_start.strftime('%d/%m/%Y')}–{range_end.strftime('%d/%m/%Y')}"
                        if excluded_rows:
                            st.info(f"{excluded_rows:,} rows were excluded because their manifested_date was missing or outside the selected range.")
                    st.success(f"Loaded {len(new):,} rows for {resolved_brand}, date selection {date_description}. Existing data outside the uploaded date(s) was retained.")
                    st.rerun()
            except Exception as e:
                st.error(f'Could not read dataset: {e}')
    if ROLE == 'Admin':
        st.caption('Existing brands are available in the dropdown. Select “➕ Add new brand” to reveal a field where you can type a new brand name.')
        st.divider(); st.subheader('Loaded brands and source data')
        data=st.session_state.dataset
        if data.empty: st.info('No datasets loaded.')
        else:
            summary=data.groupby('brand').agg(rows=('brand','size'),unique_shipments=('shipment_id','nunique') if 'shipment_id' in data.columns else ('brand','size'),couriers=('courier_name','nunique')).reset_index()
            st.caption(f"Saved dataset total: {len(data):,} source rows. Original bundled September datasets load automatically when the app starts.")
            st.markdown('**Stored brands**')
            st.caption('Delete removes that brand’s rows from the saved local dataset. Bundled source Excel files remain unchanged; use Reset to restore the bundled September datasets.')
            for _, brand_row in summary.iterrows():
                brand_name = str(brand_row['brand'])
                brand_key = ''.join(ch if ch.isalnum() else '_' for ch in brand_name.lower())
                brand_col, rows_col, shipments_col, couriers_col, action_col = st.columns([2.6, 1.15, 1.45, 1, 1.1])
                with brand_col:
                    st.write(f"**{brand_name}**")
                with rows_col:
                    st.metric('Rows', f"{int(brand_row['rows']):,}", help='Total source rows for this brand')
                    st.markdown('<style>[data-testid="stMetricValue"] { font-size: 1.8rem; white-space: nowrap; }</style>', unsafe_allow_html=True)
                with shipments_col:
                    st.metric('Unique shipments', f"{int(brand_row['unique_shipments']):,}")
                with couriers_col:
                    st.metric('Couriers', f"{int(brand_row['couriers']):,}")
                with action_col:
                    if st.button('Delete',key=f'delete_brand_{brand_key}',type='secondary'):
                        st.session_state[f'confirm_delete_brand_{brand_key}'] = True
                if st.session_state.get(f'confirm_delete_brand_{brand_key}', False):
                    st.warning(f"Delete all {int(brand_row['rows']):,} rows for {brand_name} from the saved local dataset?")
                    confirm_col, cancel_col = st.columns([1, 1])
                    with confirm_col:
                        if st.button(f"Confirm delete {brand_name}",key=f'confirm_delete_button_{brand_key}',type='primary'):
                            st.session_state.dataset = st.session_state.dataset.loc[
                                ~st.session_state.dataset['brand'].astype(str).str.casefold().eq(brand_name.casefold())
                            ].reset_index(drop=True)
                            save_dataset(st.session_state.dataset)
                            st.session_state.pop(f'confirm_delete_brand_{brand_key}', None)
                            st.success(f"Deleted {brand_name} from the saved local dataset.")
                            st.rerun()
                    with cancel_col:
                        if st.button('Cancel',key=f'cancel_delete_brand_{brand_key}'):
                            st.session_state.pop(f'confirm_delete_brand_{brand_key}', None)
                            st.rerun()

            st.divider()
            st.markdown('**Remove data for a specific brand and date**')
            st.caption('Remove one day or a date range for one brand only. Other brands and dates will be retained.')
            remove_brands = sorted(data['brand'].dropna().astype(str).unique().tolist())
            remove_brand = st.selectbox('Brand to remove from', remove_brands, key='remove_range_brand')
            removal_mode = st.radio(
                'Removal type',
                ['Single day', 'Date range'],
                horizontal=True,
                key='remove_date_mode'
            )
            if removal_mode == 'Single day':
                single_remove_date = st.date_input(
                    'Date to remove',
                    value=pd.Timestamp('2026-10-01').date(),
                    key='remove_single_date'
                )
                if st.button('Remove selected brand data for this day', type='secondary', key='remove_brand_single_date'):
                    st.session_state['pending_remove_range'] = {
                        'brand': remove_brand,
                        'mode': 'single',
                        'start': single_remove_date.isoformat(),
                        'end': single_remove_date.isoformat(),
                    }
            else:
                date_selection = st.date_input(
                    'Dates to remove',
                    value=(pd.Timestamp('2026-10-01').date(), pd.Timestamp('2026-10-05').date()),
                    key='remove_range_dates'
                )
                if not isinstance(date_selection, (tuple, list)) or len(date_selection) != 2:
                    st.info('Choose both a start date and an end date.')
                else:
                    remove_start, remove_end = date_selection
                    if st.button('Remove selected brand data for these dates', type='secondary', key='remove_brand_date_range'):
                        if remove_start > remove_end:
                            st.error('The start date must be on or before the end date.')
                        else:
                            st.session_state['pending_remove_range'] = {
                                'brand': remove_brand,
                                'mode': 'range',
                                'start': remove_start.isoformat(),
                                'end': remove_end.isoformat(),
                            }
            pending_remove = st.session_state.get('pending_remove_range')
            if pending_remove:
                if pending_remove.get('mode') == 'single':
                    st.warning(
                        f"Remove all {pending_remove['brand']} rows with manifested date "
                        f"{pending_remove['start']}? This cannot be undone unless you upload the data again."
                    )
                    confirm_label = 'Confirm single-day removal'
                else:
                    st.warning(
                        f"Remove all {pending_remove['brand']} rows with manifested dates from "
                        f"{pending_remove['start']} through {pending_remove['end']}? This cannot be undone unless you upload the data again."
                    )
                    confirm_label = 'Confirm date-range removal'
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button(confirm_label, type='primary', key='confirm_remove_range'):
                        start_remove = pd.Timestamp(pending_remove['start']).date()
                        end_remove = pd.Timestamp(pending_remove['end']).date()
                        current = st.session_state.dataset
                        row_dates = pd.to_datetime(current[DATE_COL], errors='coerce').dt.date
                        target_brand = current['brand'].astype(str).str.casefold().eq(pending_remove['brand'].casefold())
                        target_dates = row_dates.ge(start_remove) & row_dates.le(end_remove)
                        removed_count = int((target_brand & target_dates).sum())
                        st.session_state.dataset = current.loc[~(target_brand & target_dates)].reset_index(drop=True)
                        save_dataset(st.session_state.dataset)
                        st.session_state.pop('pending_remove_range', None)
                        if pending_remove.get('mode') == 'single':
                            st.success(f"Removed {removed_count:,} rows for {pending_remove['brand']} on {start_remove}. Other brands and dates were retained.")
                        else:
                            st.success(f"Removed {removed_count:,} rows for {pending_remove['brand']} from {start_remove} through {end_remove}. Other brands and dates were retained.")
                        st.rerun()
                with no_col:
                    if st.button('Cancel removal', key='cancel_remove_range'):
                        st.session_state.pop('pending_remove_range', None)
                        st.rerun()

            if st.button('Reset to bundled September datasets',type='secondary'):
                st.session_state.dataset=load_defaults()
                save_dataset(st.session_state.dataset)
                st.rerun()

elif page=='Reports':
    st.subheader('Reports & Downloads'); st.caption(filter_text)
    if selected_brand == 'Select a brand': st.info('Select a brand from the sidebar to generate a report.')
    elif filtered.empty: st.info('No data matches the selected brand and date filters.')
    else:
        kpi_row(filtered)
        st.markdown('#### Export selected analysis')
        st.write('Both downloads respect the active date and brand filters. The PDF includes the executive KPI summary, brand-wise analysis, state-wise analysis, courier-wise analysis, rule-based AI recommendations, and methodology notes. The CSV contains the filtered, cleaned shipment-level records plus normalized status flags.')
        pdf=pdf_report(filtered,'Executive Shipment Performance Report',filter_text)
        st.download_button('📄 Download executive report (PDF)',data=pdf,file_name='ShipIQ_Executive_Report.pdf',mime='application/pdf',type='primary',use_container_width=True)
        csv=filtered.drop(columns=['manifest_date'],errors='ignore').to_csv(index=False).encode('utf-8-sig')
        st.download_button('📊 Download filtered cleaned data (CSV)',data=csv,file_name='ShipIQ_Cleaned_Shipments.csv',mime='text/csv',use_container_width=True)
        st.divider(); st.markdown('#### Report preview')
        st.dataframe(rate_table(filtered,'brand'),use_container_width=True,hide_index=True)
        st.dataframe(rate_table(filtered,'courier_name'),use_container_width=True,hide_index=True)

st.divider()
st.caption('ShipIQ MVP · Abhishek Bharadwaj | abhishek@quiklee.in')

