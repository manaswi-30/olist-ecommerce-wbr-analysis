# Olist Weekly Business Review — ELT + SQL Analytics

A reproducible Python/SQLite ELT project for the Brazilian E-Commerce Public Dataset by Olist. It implements raw ingestion, cleaned staging, an order-grain mart, six SQL quality checks, five SQL analyses, chart generation, and a concise report.

## Dataset setup

Download the **Brazilian E-Commerce Public Dataset by Olist** from Kaggle:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Extract the nine CSVs into `data/raw/`, preserving the original filenames:
`olist_orders_dataset.csv`, `olist_customers_dataset.csv`, `olist_order_items_dataset.csv`, `olist_order_payments_dataset.csv`, `olist_order_reviews_dataset.csv`, `olist_products_dataset.csv`, `olist_sellers_dataset.csv`, `olist_geolocation_dataset.csv`, and `product_category_name_translation.csv`.

Raw data and the generated SQLite database are intentionally excluded from Git because they are large. Do not commit credentials or a virtual environment.

## Setup and run (Python 3.10+)

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# If PowerShell blocks activation, use:
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Or install with the active interpreter:
python -m pip install -r requirements.txt

python pipeline.py
python run_analysis.py
python -m unittest discover -s tests -v
```

To use different paths:
```bash
python pipeline.py --data-dir "D:/datasets/olist" --db "D:/work/olist.sqlite"
```
`pipeline.py --skip-quality-fail` is a diagnostic option: it records critical failures but does not stop. Normal execution exits nonzero if a configured critical check fails. The pipeline is repeatable: raw tables are replaced, staging and mart tables are rebuilt transactionally, and the mart has a unique order ID index.

## Data model

- `raw_*`: CSV-shaped source tables.
- `stg_*`: trimmed identifiers, normalized state codes, blank timestamps as NULL, and invalid negative item values as NULL.
- `mart_orders`: one row per order. Items, payments, and reviews are aggregated separately before joining to avoid fan-out. Revenue analyses use item price (excluding freight) and exclude canceled orders unless noted.

## SQL files

- `sql/quality/`: six executable quality checks. Four critical checks cover order ID integrity, delivery chronology, customer match, and review-score range. Payment reconciliation and item numeric checks are warnings. Payment mismatches are flagged, not auto-corrected, because payment flows can include vouchers, interest, and other differences.
- `sql/analysis/`: five requested analyses. Query 4 uses `customer_unique_id` and defines repeat rate over all identifiable unique customers with at least one order in the observed dataset period. Query 3 builds a calendar spine so zero-order days are retained. Query 5 defines delay as actual delivery date minus estimated delivery date; positive is late, negative is early.

## Outputs

`outputs/` contains actual SQL result CSVs, quality-check counts and affected-record samples, and generated chart PNGs. `report.pdf` is a five-page maximum report with metric definitions, findings, charts, and the VP memo.

## Reproducibility and caveats

SQLite is used to keep the project locally runnable without a database server. SQL is executed directly by SQLite; pandas is used only for output/chart presentation, not to calculate Part C results. The Olist dataset is historical (2016–2018), so results are descriptive of this observation period and should not be treated as current marketplace performance. The geolocation file is ingested as raw data but is not needed for the requested analyses.
