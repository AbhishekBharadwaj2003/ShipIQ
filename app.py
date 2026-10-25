from pathlib import Path
from io import BytesIO, StringIO
import json
import sqlite3
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
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
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:radial-gradient(ellipse at 12% 0%,rgba(53,208,197,.10),transparent 35%),#0B1220; color:var(--shipiq-ivory); }
.block-container { padding-top:1.6rem; padding-bottom:3rem; max-width:1520px; }
[data-testid="stHeader"] { background:rgba(11,18,32,.90); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#121D2D 0%,#0D1624 100%); border-right:1px solid var(--shipiq-line); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#C7D7E7; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { padding:.25rem 0; }
h1,h2,h3,h4 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; color:var(--shipiq-ivory); }
h1 { font-weight:800 !important; } h2 { font-weight:750 !important; } h3 { font-weight:700 !important; }
.shipiq-kicker { display:block; width:100%; font-size:.82rem; letter-spacing:.16em; text-transform:uppercase; color:#75FFF3 !important; -webkit-text-fill-color:#75FFF3 !important; font-weight:900; line-height:1.7; opacity:1 !important; visibility:visible !important; text-shadow:0 0 8px rgba(53,208,197,.65), 0 0 18px rgba(53,208,197,.35); margin-bottom:.5rem; overflow:visible; }
.shipiq-title { font-family:'Manrope',sans-serif; font-size:2.35rem; font-weight:800; letter-spacing:-.055em; line-height:1.08; color:var(--shipiq-ivory); }
.shipiq-sub { color:var(--shipiq-muted); font-size:1rem; margin-top:.55rem; line-height:1.65; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#19283A,#121D2D); border:1px solid var(--shipiq-line); border-radius:15px; padding:19px 20px; box-shadow:0 10px 26px rgba(0,0,0,.12); transition:transform .18s ease,border-color .18s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-2px); border-color:rgba(53,208,197,.60); }
[data-testid="stMetricLabel"] { color:#A9BED1 !important; font-size:.84rem !important; }
[data-testid="stMetricValue"] { color:var(--shipiq-ivory) !important; font-family:'Manrope',sans-serif; font-weight:800; font-size:clamp(1.2rem, 1.75vw, 1.75rem) !important; white-space:nowrap !important; overflow:visible !important; text-overflow:clip !important; letter-spacing:-.035em; }
[data-testid="stMetric"] { min-width:0; }
[data-testid="stMetric"] [data-testid="stMetricValue"] > div { white-space:nowrap !important; overflow:visible !important; text-overflow:clip !important; }
[data-testid="stMetricDelta"] { overflow:visible !important; width:100% !important; }
[data-testid="stMetricDelta"] > div { white-space:normal !important; overflow:visible !important; text-overflow:clip !important; display:flex !important; flex-wrap:wrap !important; align-items:flex-start; gap:.2rem; width:100% !important; }
[data-testid="stMetricDelta"] svg { flex-shrink:0; }
[data-testid="stMetric"] [data-testid="stMetricDelta"] p { white-space:normal !important; overflow:visible !important; text-overflow:clip !important; overflow-wrap:anywhere !important; }
[data-testid="stHorizontalBlock"] > [data-testid="column"] { min-width:0 !important; }
@media (min-width: 769px) { [data-testid="stMetricDelta"] { font-size:clamp(.62rem, .72vw, .76rem) !important; line-height:1.3 !important; } }
@media (max-width: 1100px) { [data-testid="stMetricDelta"] { font-size:.62rem !important; } }
[data-testid="stMetricDelta"] { color:var(--shipiq-gold) !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--shipiq-line) !important; border-radius:15px !important; }
[data-testid="stExpander"] { border:1px solid var(--shipiq-line); border-radius:12px; background:rgba(32,32,32,.7); }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid var(--shipiq-line); border-radius:12px; overflow:hidden; }
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stDateInput"] input,[data-testid="stSelectbox"] [data-baseweb="select"] > div,[data-testid="stMultiSelect"] [data-baseweb="select"] > div,[data-testid="stTextArea"] textarea { background:#172638 !important; border-color:#355268 !important; border-radius:9px !important; color:var(--shipiq-ivory) !important; }
[data-testid="stFileUploader"] section { background:rgba(18,29,45,.78); border:1px dashed #3D7180; border-radius:12px; }
[data-testid="stFileUploader"] section:hover { border-color:var(--shipiq-gold); }
.stButton > button,[data-testid="stFormSubmitButton"] > button { border-radius:9px; border:1px solid #35D0C5; background:linear-gradient(110deg,#35D0C5,#159AAB); color:#071B25; font-weight:700; padding:.55rem 1rem; box-shadow:none; transition:transform .16s ease,filter .16s ease; }
.stButton > button:hover,[data-testid="stFormSubmitButton"] > button:hover { filter:brightness(1.08); transform:translateY(-1px); border-color:#8CF2E9; color:#071B25; }
.stButton > button[kind="secondary"] { background:#1A2B3D; border-color:#4A453C; color:#E3F6FF; box-shadow:none; }
[data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--shipiq-line); }
[data-baseweb="tab"] { background:transparent; border-radius:9px 9px 0 0; padding:.65rem 1rem; color:#B8B0A4; }
[data-baseweb="tab"][aria-selected="true"] { color:var(--shipiq-gold); border-bottom-color:var(--shipiq-gold); }
hr { border-color:var(--shipiq-line); } a { color:var(--shipiq-gold) !important; }
[data-testid="stPlotlyChart"] { background:rgba(32,32,32,.55); border:1px solid var(--shipiq-line); border-radius:13px; padding:.35rem; }
.stAlert { border-radius:12px; border:1px solid var(--shipiq-line); }
@media (max-width:768px) { .block-container{padding-left:1rem;padding-right:1rem;} .shipiq-title{font-size:1.9rem;} [data-testid="stMetric"]{padding:13px;border-radius:12px;} }
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

# Local SQLite database designed for ongoing multi-brand, multi-month shipment history.
# Each shipment row is stored separately with indexed brand/date fields; payload_json preserves
# the flexible source columns without forcing every brand to have an identical schema.
DB_PATH = APP_DIR / 'shipiq_data.sqlite3'

def _init_database(conn):
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            manifested_date TEXT,
            shipment_id TEXT,
            payload_json TEXT NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_shipments_brand_date ON shipments(brand, manifested_date)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_shipments_id ON shipments(shipment_id)')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shipiq_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    conn.commit()

def save_dataset(dataset):
    # Use a transaction so the prior saved dataset remains intact if writing fails.
    records_json = dataset.to_json(orient='records', date_format='iso', date_unit='ms')
    records = json.loads(records_json) if records_json else []
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        _init_database(conn)
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM shipments')
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
        conn.executemany(
            'INSERT INTO shipments (brand, manifested_date, shipment_id, payload_json) VALUES (?, ?, ?, ?)',
            rows
        )
        conn.execute(
            "INSERT INTO shipiq_metadata (key, value) VALUES ('schema_version', '2') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )
        conn.commit()

def load_persisted_dataset():
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        _init_database(conn)
        rows = conn.execute('SELECT payload_json FROM shipments ORDER BY id').fetchall()
        # Migrate the previous single-JSON-row storage format automatically, if present.
        if not rows:
            old_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='shipiq_state'"
            ).fetchone()
            if old_table:
                legacy = conn.execute('SELECT dataset_json FROM shipiq_state WHERE id = 1').fetchone()
                if legacy and legacy[0]:
                    old_records = json.loads(legacy[0])
                    if old_records:
                        legacy_df = pd.DataFrame(old_records)
                        # Save in the new row-based schema after leaving this connection.
                        migrated = legacy_df
                    else:
                        migrated = pd.DataFrame()
                else:
                    migrated = None
            else:
                migrated = None
        else:
            migrated = pd.DataFrame([json.loads(row[0]) for row in rows])
    if not rows:
        if migrated is None:
            return None
        save_dataset(migrated)
        stored = migrated
    else:
        stored = pd.DataFrame([json.loads(row[0]) for row in rows])
    if stored.empty or 'brand' not in stored.columns:
        return stored
    parts = []
    for brand, group in stored.groupby('brand', dropna=False, sort=False):
        parts.append(clean_df(group, str(brand)))
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()

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

def rate_table(df, by):
    if df.empty: return pd.DataFrame()
    # Count source rows, not non-null shipment IDs, so missing IDs cannot silently lower shipment totals.
    g=df.groupby(by, dropna=False).agg(shipments=('normalized_status','size'), delivered=('is_delivered','sum'), rto=('is_rto','sum'), cancelled=('is_cancelled','sum'), finalized=('is_final','sum')).reset_index()
    g['delivery_rate_%']=np.where(g.finalized>0,100*g.delivered/g.finalized,0).round(1)
    g['rto_rate_%']=np.where(g.finalized>0,100*g.rto/g.finalized,0).round(1)
    g['cancellation_rate_%']=np.where(g.finalized>0,100*g.cancelled/g.finalized,0).round(1)
    return g.sort_values(['delivery_rate_%','shipments'],ascending=[False,False])

def pdf_report(df, title, filters_text):
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28)
    styles=getSampleStyleSheet(); story=[]
    story.append(Paragraph('ShipIQ | Shipment Intelligence',styles['Title']))
    story.append(Paragraph(title,styles['Heading2']))
    story.append(Paragraph(filters_text,styles['Normal'])); story.append(Spacer(1,12))
    m=metrics(df)
    summary=[['Metric','Value'],['Total shipments',f"{m['Shipments']:,}"],['Delivered',f"{m['Delivered']:,}"],['Delivery rate (finalized shipments)',f"{m['Delivery rate']:.1f}%"],['RTO',f"{m['RTO']:,}"],['RTO rate (finalized shipments)',f"{m['RTO rate']:.1f}%"],['Cancelled',f"{m['Cancelled']:,}"],['Cancellation rate (finalized shipments)',f"{m['Cancellation rate']:.1f}%"],['Pending / in progress',f"{m['Pending / in progress']:,}"],['Unknown / unmapped status',f"{m['Unknown / unmapped status']:,}"]]
    t=Table(summary,colWidths=[270,150]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17243b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.35,colors.lightgrey),('PADDING',(0,0),(-1,-1),7)])); story.append(t); story.append(Spacer(1,14))
    story.append(Paragraph('Brand summary',styles['Heading3']))
    if 'brand' in df.columns:
        b=rate_table(df,'brand'); rows=[['Brand','Shipments','Delivered','Delivery %','RTO','RTO %','Cancelled']]
        for _,r in b.iterrows(): rows.append([str(r['brand']),int(r.shipments),int(r.delivered),f"{r['delivery_rate_%']:.1f}%",int(r.rto),f"{r['rto_rate_%']:.1f}%",int(r.cancelled)])
        bt=Table(rows,repeatRows=1); bt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17243b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('PADDING',(0,0),(-1,-1),5)])); story.append(bt); story.append(Spacer(1,12))
    story.append(Paragraph('Courier performance',styles['Heading3']))
    c=rate_table(df,'courier_name'); rows=[['Courier','Shipments','Delivered','Delivery %','RTO','RTO %','Cancelled']]
    for _,r in c.head(25).iterrows(): rows.append([str(r['courier_name'])[:32],int(r.shipments),int(r.delivered),f"{r['delivery_rate_%']:.1f}%",int(r.rto),f"{r['rto_rate_%']:.1f}%",int(r.cancelled)])
    ct=Table(rows,repeatRows=1); ct.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17243b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('PADDING',(0,0),(-1,-1),4)])); story.append(ct)
    story.append(Spacer(1,10)); story.append(Paragraph('Methodology: delivery, RTO and cancellation rates use finalized shipments as the denominator. Pending/in-progress shipments are excluded from these rate denominators. Shipment status is normalized from the source status field; validate status mapping before operational decisions.',styles['Italic']))
    doc.build(story); buf.seek(0); return buf.getvalue()

if 'dataset' not in st.session_state:
    persisted_dataset = load_persisted_dataset()
    if persisted_dataset is None:
        st.session_state.dataset = load_defaults()
        save_dataset(st.session_state.dataset)
    else:
        st.session_state.dataset = persisted_dataset
if 'custom_brands' not in st.session_state: st.session_state.custom_brands=[]

with st.sidebar:
    st.markdown('## 📦 ShipIQ')
    st.caption('Shipment Intelligence Control Tower')
    page=st.radio('NAVIGATION',['Executive Overview','Brand-wise Analysis','AI Recommendation','State-wise Analysis','Courier-wise Analysis','Data Management','Reports'],label_visibility='collapsed')
    st.divider()
    all_data=st.session_state.dataset.copy()
    if not all_data.empty:
        dates=pd.to_datetime(all_data[DATE_COL],errors='coerce').dropna()
        if not dates.empty:
            min_d,max_d=dates.min().date(),dates.max().date()
            mode=st.radio('Date filter',['Date range','Single date'],horizontal=False)
            if mode=='Single date':
                chosen=st.date_input('Manifested date',value=max_d,min_value=min_d,max_value=max_d)
                start_d=end_d=chosen
            else:
                selected=st.date_input('Manifested date range',value=(min_d,max_d),min_value=min_d,max_value=max_d)
                if isinstance(selected,tuple) and len(selected)==2: start_d,end_d=selected
                else: start_d=end_d=selected
            brands=sorted(all_data['brand'].dropna().astype(str).unique().tolist())
            chosen_brands=st.multiselect('Brand filter',brands,default=brands)
            st.caption('Dates are based on manifested_date.')
        else:
            start_d=end_d=None; chosen_brands=sorted(all_data['brand'].dropna().astype(str).unique().tolist())
    else:
        start_d=end_d=None; chosen_brands=[]
        st.info('Upload a dataset in Data Management to begin.')

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

filter_text=f"Manifested date: {start_d or 'All'} to {end_d or 'All'} | Brands: {', '.join(chosen_brands) if chosen_brands else 'None'}"

st.markdown('<div class="shipiq-kicker">PATTERNS · LOGISTICS INTELLIGENCE</div>',unsafe_allow_html=True)
st.markdown('<div class="shipiq-title">ShipIQ</div>',unsafe_allow_html=True)
st.markdown('<div class="shipiq-sub">A clearer view of shipment health, courier performance, and delivery outcomes.</div>',unsafe_allow_html=True)
st.write('')

if page=='Executive Overview':
    st.subheader('Executive Overview')
    st.caption(filter_text)
    if filtered.empty: st.info('No shipments match the current filters. Upload data or adjust the date/brand filters.')
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
    if filtered.empty: st.info('No data for the selected filters.')
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
    if filtered.empty:
        st.info('No shipments match the selected dates and brands. Adjust the filters to generate recommendations.')
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
    if filtered.empty: st.info('No data for the selected filters.')
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
    if filtered.empty: st.info('No data for the selected filters.')
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
    st.markdown('Upload shipment files, choose a single dataset date or a date range, and assign the data to an existing brand or create a new brand. Uploaded data is saved to a local SQLite database and survives browser refreshes and app restarts on this machine.')

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
            brand_col, rows_col, shipments_col, couriers_col, action_col = st.columns([3, 1, 1.4, 1, 1.2])
            with brand_col:
                st.write(f"**{brand_name}**")
            with rows_col:
                st.metric('Rows', f"{int(brand_row['rows']):,}")
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
        st.markdown('**Remove data for a specific brand and date range**')
        st.caption('Use this to remove a test upload (for example, Freely from 01–05 October) without deleting the brand’s other dates.')
        remove_brands = sorted(data['brand'].dropna().astype(str).unique().tolist())
        remove_brand = st.selectbox('Brand to remove from', remove_brands, key='remove_range_brand')
        remove_start, remove_end = st.date_input(
            'Dates to remove',
            value=(pd.Timestamp('2026-10-01').date(), pd.Timestamp('2026-10-05').date()),
            key='remove_range_dates'
        )
        if st.button('Remove selected brand data for these dates', type='secondary', key='remove_brand_date_range'):
            if not isinstance(remove_start, type(pd.Timestamp.today().date())) or not isinstance(remove_end, type(pd.Timestamp.today().date())):
                st.error('Choose both a start date and an end date.')
            elif remove_start > remove_end:
                st.error('The start date must be on or before the end date.')
            else:
                st.session_state['pending_remove_range'] = {
                    'brand': remove_brand,
                    'start': remove_start.isoformat(),
                    'end': remove_end.isoformat(),
                }
        pending_remove = st.session_state.get('pending_remove_range')
        if pending_remove:
            st.warning(
                f"Remove all {pending_remove['brand']} rows with manifested dates from "
                f"{pending_remove['start']} through {pending_remove['end']}? This cannot be undone unless you upload the data again."
            )
            yes_col, no_col = st.columns(2)
            with yes_col:
                if st.button('Confirm date-range removal', type='primary', key='confirm_remove_range'):
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
    if filtered.empty: st.info('No data matches the current filters. Adjust filters or upload data first.')
    else:
        kpi_row(filtered)
        st.markdown('#### Export selected analysis')
        st.write('Both downloads respect the active date and brand filters. The PDF contains an executive KPI summary, brand summary, courier performance table, and methodology note. The CSV contains the filtered, cleaned shipment-level records plus normalized status flags.')
        pdf=pdf_report(filtered,'Executive Shipment Performance Report',filter_text)
        st.download_button('📄 Download executive report (PDF)',data=pdf,file_name='ShipIQ_Executive_Report.pdf',mime='application/pdf',type='primary',use_container_width=True)
        csv=filtered.drop(columns=['manifest_date'],errors='ignore').to_csv(index=False).encode('utf-8-sig')
        st.download_button('📊 Download filtered cleaned data (CSV)',data=csv,file_name='ShipIQ_Cleaned_Shipments.csv',mime='text/csv',use_container_width=True)
        st.divider(); st.markdown('#### Report preview')
        st.dataframe(rate_table(filtered,'brand'),use_container_width=True,hide_index=True)
        st.dataframe(rate_table(filtered,'courier_name'),use_container_width=True,hide_index=True)

st.divider()
st.caption('ShipIQ MVP · September 2026 Patterns shipment exports · Rates are descriptive and use finalized shipments as denominator. Always validate status mappings and source definitions before operational decisions.')
