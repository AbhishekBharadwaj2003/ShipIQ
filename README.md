# ShipIQ — Shipment Intelligence Control Tower

ShipIQ is a Streamlit-based shipment analytics dashboard that turns multi-brand shipping data into operational KPIs, courier comparisons, date-aware trends, and actionable business recommendations. It is designed for ongoing analysis of shipment exports across brands and reporting periods.

> **Data note:** The repository includes bundled September 2026 starter datasets for Freely, Kotart, and BigBearFarms. Sample or synthetic data should be clearly distinguished from real operational records.

## Key features

- **Executive Overview** — manifested shipments, delivered shipments, RTO delivered, cancellations, delivery rate, and RTO rate.
- **Date and brand filters** — analyse a single manifested date or a date range across one or more brands.
- **Day-over-day comparisons** — when a single date is selected, compare KPI counts and rate changes with the previous calendar day when data is available.
- **Brand-wise Analysis** — per-brand KPI summaries, daily manifested shipment trends, and courier performance.
- **AI Recommendation** — KPI-driven, brand-specific recommendations for delivery performance, RTO, cancellations, pending shipments, status mapping, and courier allocation. This version uses transparent rules based on the selected data rather than an external generative-AI model.
- **State-wise Analysis** — compare outcomes by destination state and review courier performance within a state.
- **Courier-wise Analysis** — evaluate courier volumes and shipment outcomes.
- **Data Management** — upload CSV/XLSX exports, add brands, upload single-date or date-range data, and remove a brand's records for a selected date range.
- **Reports** — generate a report from the currently selected data.
- **Persistent local storage** — local SQLite storage saves the combined shipment dataset between refreshes and app restarts on the same machine.
- **Data quality checks** — normalize source shipment statuses and support analysis of missing or unmapped values.

## Tech stack

- Python
- Streamlit
- Pandas and NumPy
- Plotly
- SQLite
- ReportLab

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/AbhishekBharadwaj2003/ShipIQ.git
cd ShipIQ
```

### 2. Create and activate a virtual environment (recommended)

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

If a `requirements.txt` file is present:

```bash
pip install -r requirements.txt
```

Otherwise, install the core packages:

```bash
pip install streamlit pandas numpy plotly reportlab openpyxl
```

### 4. Run ShipIQ

```bash
python -m streamlit run app.py
```

Streamlit will display a local URL, usually `http://localhost:8501`.

## Using the dashboard

1. Choose a page from the sidebar.
2. Select **Single date** or **Date range** using the manifested date.
3. Select one or more brands.
4. Review the KPI cards and charts.
5. Open **AI Recommendation** to see recommendations for each brand in the selected period.
6. Use **Data Management** to upload additional CSV/XLSX shipment exports.

### Adding date-range data

For a date-range upload, the file must contain a valid `manifested_date` column. Select the brand and the inclusive start/end dates. When replacing data for an existing brand and range, the app is designed to replace that brand's records within the selected range while retaining records outside it.

For a single-date upload, the selected date is applied to the uploaded rows.

## Persistence and backups

On local runs, ShipIQ stores its working dataset in `shipiq_data.sqlite3` in the project directory. Keep a backup of this file, especially before large uploads, date-range replacements, or resets. The **Reset to bundled September datasets** action replaces the saved working dataset with the bundled starter data.

**Important hosting note:** SQLite stored on a local app filesystem is suitable for a personal local deployment, but it is not reliable persistent storage on ephemeral hosting platforms. For a Streamlit Cloud or multi-user deployment, configure a managed database (for example, PostgreSQL) and appropriate secrets/credentials before relying on it for long-term data retention. Do not commit real shipment data, credentials, customer personal information, or the SQLite database to a public repository.

## KPI definitions

- **Manifested:** number of shipment rows in the selected data.
- **Delivered / RTO / Cancelled:** counts based on normalized shipment status.
- **Delivery rate and RTO rate:** calculated from completed delivery and completed RTO outcomes, according to the app's KPI logic. Check the on-screen methodology note when interpreting rates.
- **Day-over-day changes:** compare the selected single date with the previous calendar date when records exist for that date. Rate changes are shown in percentage points.

Recommendations are intended to support operational investigation, not replace business judgment. Courier or brand comparisons should be interpreted alongside shipment counts, service levels, order mix, and source-data quality.

## Repository

- **GitHub:** https://github.com/AbhishekBharadwaj2003/ShipIQ

## License

No license is specified yet. Add a license file if you intend to grant others permission to reuse, modify, or distribute this project.
