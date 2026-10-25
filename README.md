# ShipIQ — Shipment Intelligence Control Tower

A Streamlit MVP for analysing Patterns shipping aggregator shipment exports. Bundled starter data covers September 2026 for Freely, Kotart, and BigBearFarms.

## Features
- Executive overview with shipment KPIs, daily manifested trend, and status mix
- Separate brand-wise analytics
- State-wise performance and best courier by destination state
- Courier-wise performance and volume thresholds
- Sidebar filters for a single manifested date or date range, plus brand selection
- Data management to upload CSV/Excel exports and add/replace a brand in the current session
- Filter-aware PDF executive report and cleaned CSV downloads

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL Streamlit prints, typically `http://localhost:8501`.

## Data expectations
Patterns exports should include `manifested_date`, `shipment_status`, `courier_name`, and `drop_location_state`. `shipment_id` is recommended. Other fields are retained when present. Excel and CSV uploads are supported.

## KPI definitions
- **Manifested shipments:** rows in the selected period, using `manifested_date`.
- **Delivery rate:** Delivered / finalized shipments.
- **RTO rate:** RTO / finalized shipments.
- **Cancellation rate:** Cancelled / finalized shipments.
- **Finalized shipments:** normalized Delivered, RTO, Cancelled, Lost/Damaged, or Failed/Undelivered status.
- Pending/in-progress statuses are excluded from rate denominators so open shipments do not artificially lower outcome rates.

Status normalization is heuristic and should be reviewed against the source platform's official status definitions before making operational decisions. Explicitly completed RTO statuses (such as `RTO Delivered`) are counted as RTO outcomes; RTO workflows still in transit, out for delivery, or requested are treated as in progress. Failed and undelivered statuses are not counted as successful deliveries. Unknown/unmapped statuses are tracked separately from known pending/in-progress shipments. Courier rankings are descriptive; compare rates with shipment counts and avoid overinterpreting low-volume groups.

The Data Management page includes validation checks for missing/invalid dates, missing status/courier/state/shipment IDs, repeated shipment IDs, and unrecognized statuses. Repeated IDs and rows with missing IDs are flagged rather than silently removed. Group shipment counts are based on source rows, while unique shipment counts are shown separately.

## Current limitations
- Uploaded datasets persist only for the current Streamlit session; there is no database or multi-user persistence yet.
- Date filtering is based on manifested date.
- PDF exports include KPI summaries and brand/courier tables. Full chart rendering and custom report sections can be added in a later iteration.
- The original files contain shipment-level information. Keep this project private and avoid publishing raw data publicly.
