from pathlib import Path
from io import BytesIO
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
:root { --shipiq-ink:#152238; }
.block-container {padding-top:1.3rem; padding-bottom:2rem; max-width:1500px;}
[data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.18)}
.shipiq-kicker {font-size:.76rem;letter-spacing:.18em;text-transform:uppercase;color:#6b8afd;font-weight:700}
.shipiq-title {font-size:2.05rem;font-weight:800;letter-spacing:-.04em;line-height:1.1}
.shipiq-sub {color:#8b95a7;font-size:.95rem;margin-top:.4rem}
[data-testid="stMetric"] {background:rgba(128,128,128,.06);border:1px solid rgba(128,128,128,.13);padding:15px 17px;border-radius:14px}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_excel(path, brand):
    df = pd.read_excel(path)
    df['brand'] = brand
    return df

def normalize_status(v):
    """Map source statuses to outcome groups without treating 'undelivered' as 'delivered'."""
    if pd.isna(v) or not str(v).strip():
        return 'Unknown'
    s = re.sub(r'\s+', ' ', str(v).strip().lower())
    # Outcomes that must take precedence over the substring "deliver".
    if any(x in s for x in ['rto', 'return to origin', 'returned to origin', 'return-to-origin']):
        return 'RTO'
    if any(x in s for x in ['cancel', 'voided']):
        return 'Cancelled'
    if any(x in s for x in ['undeliver', 'not delivered', 'delivery failed', 'failed delivery',
                            'failed', 'exception', 'attempt failed', 'non-delivery']):
        return 'Failed/Undelivered'
    if any(x in s for x in ['lost', 'damage', 'destroy']):
        return 'Lost/Damaged'
    # "Out for delivery" and "delivery attempted" are not successful deliveries.
    if any(x in s for x in ['out for delivery', 'delivery attempted', 'attempting delivery',
                            'transit', 'shipped', 'picked', 'ndr', 'reached',
                            'in warehouse', 'in hub', 'pickup complete', 'picked up']):
        return 'In Transit/Attempting'
    if any(x in s for x in ['manifest', 'pickup pending', 'ready to ship', 'label', 'booked']):
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
            'Rows with missing destination state': 0, 'Duplicate shipment-ID rows': 0,
            'Unknown/unmapped status rows': 0,
        }
    duplicate_rows = 0
    if 'shipment_id' in df.columns:
        ids = df['shipment_id'].astype('string').str.strip()
        valid_ids = ids.notna() & ids.ne('')
        duplicate_rows = int(ids[valid_ids].duplicated(keep=False).sum())
    known = {'Delivered', 'RTO', 'Cancelled', 'Lost/Damaged', 'Failed/Undelivered',
             'Manifested/Pending', 'In Transit/Attempting', 'Unknown'}
    return {
        'Rows loaded': int(len(df)),
        'Rows with invalid/missing manifested date': int(pd.to_datetime(df.get(DATE_COL, pd.Series(index=df.index, dtype='object')), errors='coerce').isna().sum()),
        'Rows with missing shipment status': int(df[STATUS_COL].isna().sum()) if STATUS_COL in df.columns else int(len(df)),
        'Rows with missing courier': int(df['courier_name'].isna().sum() + df['courier_name'].astype('string').str.strip().eq('').sum()) if 'courier_name' in df.columns else int(len(df)),
        'Rows with missing destination state': int(df['drop_location_state'].isna().sum() + df['drop_location_state'].astype('string').str.strip().eq('').sum()) if 'drop_location_state' in df.columns else int(len(df)),
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

def rate(num, den): return (100*num/den) if den else 0.0

def metrics(df):
    total=len(df); delivered=int(df['is_delivered'].sum()); rto=int(df['is_rto'].sum()); cancelled=int(df['is_cancelled'].sum()); final=int(df['is_final'].sum())
    return {'Shipments':total,'Delivered':delivered,'Delivery rate':rate(delivered,final),'RTO':rto,'RTO rate':rate(rto,final),'Cancelled':cancelled,'Cancellation rate':rate(cancelled,final),'Finalized':final,'Pending / in progress':total-final}

def kpi_row(df):
    m=metrics(df)
    cols=st.columns(6)
    vals=[('Shipments',f"{m['Shipments']:,}"),('Delivered',f"{m['Delivered']:,}"),('Delivery rate',f"{m['Delivery rate']:.1f}%"),('RTO rate',f"{m['RTO rate']:.1f}%"),('Cancellations',f"{m['Cancelled']:,}"),('Pending / in progress',f"{m['Pending / in progress']:,}")]
    for c,(label,val) in zip(cols,vals): c.metric(label,val)

def rate_table(df, by):
    if df.empty: return pd.DataFrame()
    g=df.groupby(by, dropna=False).agg(shipments=('shipment_id' if 'shipment_id' in df.columns else 'brand','size'), delivered=('is_delivered','sum'), rto=('is_rto','sum'), cancelled=('is_cancelled','sum'), finalized=('is_final','sum')).reset_index()
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
    summary=[['Metric','Value'],['Total shipments',f"{m['Shipments']:,}"],['Delivered',f"{m['Delivered']:,}"],['Delivery rate (finalized shipments)',f"{m['Delivery rate']:.1f}%"],['RTO',f"{m['RTO']:,}"],['RTO rate (finalized shipments)',f"{m['RTO rate']:.1f}%"],['Cancelled',f"{m['Cancelled']:,}"],['Cancellation rate (finalized shipments)',f"{m['Cancellation rate']:.1f}%"],['Pending / in progress',f"{m['Pending / in progress']:,}"]]
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
    st.session_state.dataset = load_defaults()
if 'custom_brands' not in st.session_state: st.session_state.custom_brands=[]

with st.sidebar:
    st.markdown('## 📦 ShipIQ')
    st.caption('Shipment Intelligence Control Tower')
    page=st.radio('NAVIGATION',['Executive Overview','Brand-wise Analysis','State-wise Analysis','Courier-wise Analysis','Data Management','Reports'],label_visibility='collapsed')
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
        kpi_row(filtered)
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
            signals.append(f"**{m['Pending / in progress']:,} shipments** are not currently classified as finalized; treat rates as provisional until more shipments reach a final outcome.")
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
    st.markdown('Upload shipment files and assign a brand. Excel (.xlsx/.xls) and CSV are supported. Uploaded files are added to the current app session; persistent multi-user storage can be added later.')
    with st.form('upload_form',clear_on_submit=True):
        up=st.file_uploader('Choose shipment dataset',type=['xlsx','xls','csv'])
        brand_name=st.text_input('Brand name',placeholder='e.g. NewBrand')
        submitted=st.form_submit_button('Validate and add dataset',type='primary')
    if submitted:
        if up is None or not brand_name.strip(): st.error('Choose a file and enter a brand name.')
        else:
            try:
                new=pd.read_csv(up) if up.name.lower().endswith('.csv') else pd.read_excel(up)
                if new.empty: st.error('The uploaded file has no rows.')
                elif DATE_COL not in new.columns: st.error(f"Required column '{DATE_COL}' was not found. Please upload a Patterns export with a manifested_date column.")
                elif STATUS_COL not in new.columns: st.error(f"Required column '{STATUS_COL}' was not found.")
                else:
                    new=clean_df(new,brand_name.strip())
                    old=st.session_state.dataset
                    # Re-uploading a brand replaces that brand in this session to prevent accidental double counting.
                    old=old[old.brand.astype(str).str.casefold()!=brand_name.strip().casefold()] if not old.empty else old
                    st.session_state.dataset=pd.concat([old,new],ignore_index=True,sort=False)
                    st.success(f"Added {len(new):,} rows for {brand_name.strip()}. Existing rows for that brand in this session were replaced.")
                    st.rerun()
            except Exception as e: st.error(f'Could not read dataset: {e}')
    st.divider(); st.subheader('Loaded brands and source data')
    data=st.session_state.dataset
    if data.empty: st.info('No datasets loaded.')
    else:
        summary=data.groupby('brand').agg(rows=('brand','size'),unique_shipments=('shipment_id','nunique') if 'shipment_id' in data.columns else ('brand','size'),couriers=('courier_name','nunique')).reset_index()
        st.dataframe(summary,use_container_width=True,hide_index=True)
        st.caption(f"Current session total: {len(data):,} source rows. Original bundled September datasets load automatically when the app starts.")

        st.subheader('Data quality validation')
        quality = data_quality_summary(data)
        q1, q2 = st.columns(2)
        with q1:
            st.dataframe(pd.DataFrame({'Check': list(quality.keys()), 'Count': list(quality.values())}),
                         use_container_width=True, hide_index=True)
        with q2:
            status_check = data.groupby(['shipment_status', 'normalized_status'], dropna=False).size().reset_index(name='rows') if STATUS_COL in data.columns else pd.DataFrame()
            if not status_check.empty:
                st.markdown('**Source status → normalized status**')
                st.dataframe(status_check.sort_values('rows', ascending=False), use_container_width=True, hide_index=True)
        if quality['Duplicate shipment-ID rows']:
            st.warning(f"Found {quality['Duplicate shipment-ID rows']:,} rows whose shipment ID appears more than once. These rows are retained, not silently removed; confirm whether repeated IDs are valid records before interpreting totals.")
        if quality['Rows with invalid/missing manifested date']:
            st.warning(f"{quality['Rows with invalid/missing manifested date']:,} rows have no usable manifested date and will be excluded from date-filtered views.")
        if quality['Unknown/unmapped status rows']:
            st.warning(f"{quality['Unknown/unmapped status rows']:,} rows have source statuses outside the recognized outcome groups. Review the mapping before relying on outcome rates.")
        with st.expander('Preview combined data'): st.dataframe(data.head(100),use_container_width=True)
        if st.button('Reset to bundled September datasets',type='secondary'):
            st.session_state.dataset=load_defaults(); st.rerun()

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
