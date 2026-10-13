#!/usr/bin/env python3
"""Reproducible Olist ELT pipeline: raw CSVs -> staging -> one-row-per-order mart."""
from __future__ import annotations
import argparse, logging, sqlite3, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data" / "raw"
DEFAULT_DB = ROOT / "data" / "olist_wbr.sqlite"
LOG = logging.getLogger("olist_pipeline")

REQUIRED = {
 "olist_orders_dataset.csv": {"order_id","customer_id","order_status","order_purchase_timestamp","order_delivered_customer_date","order_estimated_delivery_date"},
 "olist_customers_dataset.csv": {"customer_id","customer_unique_id","customer_state","customer_city"},
 "olist_order_items_dataset.csv": {"order_id","order_item_id","product_id","price","freight_value"},
 "olist_order_payments_dataset.csv": {"order_id","payment_value"},
 "olist_order_reviews_dataset.csv": {"order_id","review_score"},
 "olist_products_dataset.csv": {"product_id","product_category_name"},
 "product_category_name_translation.csv": {"product_category_name","product_category_name_english"},
 "olist_sellers_dataset.csv": {"seller_id","seller_state"},
 "olist_geolocation_dataset.csv": {"geolocation_zip_code_prefix","geolocation_state"},
}
DATE_COLS = {
 "olist_orders_dataset.csv": ["order_purchase_timestamp","order_approved_at","order_delivered_carrier_date","order_delivered_customer_date","order_estimated_delivery_date"],
 "olist_order_items_dataset.csv": ["shipping_limit_date"],
 "olist_order_reviews_dataset.csv": ["review_creation_date","review_answer_timestamp"],
}

def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

def load_raw(conn, data_dir: Path):
    import csv
    for filename, required in REQUIRED.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Required input file is missing: {path}")
        LOG.info("Loading raw file %s", filename)
        table_stem = filename.removesuffix(".csv").replace("olist_", "").replace("_dataset", "")
        table = "raw_" + table_stem.replace("product_category_name_translation", "category_translation")
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            columns = reader.fieldnames or []
            missing = required - set(columns)
            if missing:
                raise ValueError(f"{filename} is missing required columns: {sorted(missing)}")
            quoted_cols = ",".join('"' + c.replace('"','""') + '"' for c in columns)
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.execute(f'CREATE TABLE "{table}" ({quoted_cols})')
            placeholders = ",".join("?" for _ in columns)
            insert = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders})'
            batch=[]; count=0
            for row in reader:
                batch.append(tuple(row.get(c) for c in columns))
                if len(batch) >= 10000:
                    conn.executemany(insert,batch); count += len(batch); batch=[]
            if batch:
                conn.executemany(insert,batch); count += len(batch)
        LOG.info("Loaded %s rows into %s", count, table)

def create_staging(conn):
    LOG.info("Building cleaned staging tables")
    # Rebuild staging deterministically from raw tables each run.
    conn.executescript("""
    BEGIN IMMEDIATE;
    DROP TABLE IF EXISTS stg_orders;
    CREATE TABLE stg_orders AS
    SELECT TRIM(order_id) order_id, TRIM(customer_id) customer_id, order_status,
      NULLIF(TRIM(order_purchase_timestamp),'') order_purchase_timestamp,
      NULLIF(TRIM(order_approved_at),'') order_approved_at,
      NULLIF(TRIM(order_delivered_carrier_date),'') order_delivered_carrier_date,
      NULLIF(TRIM(order_delivered_customer_date),'') order_delivered_customer_date,
      NULLIF(TRIM(order_estimated_delivery_date),'') order_estimated_delivery_date
    FROM raw_orders WHERE order_id IS NOT NULL AND TRIM(order_id) <> '';

    DROP TABLE IF EXISTS stg_customers;
    CREATE TABLE stg_customers AS
    SELECT TRIM(customer_id) customer_id, TRIM(customer_unique_id) customer_unique_id,
      TRIM(customer_city) customer_city, UPPER(TRIM(customer_state)) customer_state
    FROM raw_customers WHERE customer_id IS NOT NULL AND TRIM(customer_id) <> '';

    DROP TABLE IF EXISTS stg_items;
    CREATE TABLE stg_items AS
    SELECT TRIM(order_id) order_id, CAST(order_item_id AS INTEGER) order_item_id,
      TRIM(product_id) product_id, TRIM(seller_id) seller_id,
      CASE WHEN CAST(price AS REAL) >= 0 THEN CAST(price AS REAL) END price,
      CASE WHEN CAST(freight_value AS REAL) >= 0 THEN CAST(freight_value AS REAL) END freight_value
    FROM raw_order_items WHERE order_id IS NOT NULL AND TRIM(order_id) <> '';

    DROP TABLE IF EXISTS stg_payments;
    CREATE TABLE stg_payments AS
    SELECT TRIM(order_id) order_id, payment_type,
      CASE WHEN CAST(payment_value AS REAL) >= 0 THEN CAST(payment_value AS REAL) END payment_value
    FROM raw_order_payments WHERE order_id IS NOT NULL AND TRIM(order_id) <> '';

    DROP TABLE IF EXISTS stg_reviews;
    CREATE TABLE stg_reviews AS
    SELECT TRIM(order_id) order_id,
      CASE WHEN CAST(review_score AS INTEGER) BETWEEN 1 AND 5 THEN CAST(review_score AS INTEGER) END review_score
    FROM raw_order_reviews WHERE order_id IS NOT NULL AND TRIM(order_id) <> '';

    DROP TABLE IF EXISTS stg_products;
    CREATE TABLE stg_products AS
    SELECT TRIM(product_id) product_id, NULLIF(TRIM(product_category_name),'') product_category_name
    FROM raw_products WHERE product_id IS NOT NULL AND TRIM(product_id) <> '';

    DROP TABLE IF EXISTS stg_category_translation;
    CREATE TABLE stg_category_translation AS
    SELECT TRIM(product_category_name) product_category_name,
      TRIM(product_category_name_english) product_category_name_english
    FROM raw_category_translation;

    CREATE INDEX IF NOT EXISTS ix_stg_orders_customer ON stg_orders(customer_id);
    CREATE INDEX IF NOT EXISTS ix_stg_items_order ON stg_items(order_id);
    CREATE INDEX IF NOT EXISTS ix_stg_payments_order ON stg_payments(order_id);
    CREATE INDEX IF NOT EXISTS ix_stg_reviews_order ON stg_reviews(order_id);
    COMMIT;
    """)
    LOG.info("Staging complete")

def create_mart(conn):
    LOG.info("Building order mart")
    conn.executescript("""
    BEGIN IMMEDIATE;
    DROP TABLE IF EXISTS mart_orders;
    CREATE TABLE mart_orders AS
    WITH item_agg AS (
      SELECT order_id, COUNT(*) AS item_count,
        SUM(COALESCE(price,0)) AS item_total,
        SUM(COALESCE(freight_value,0)) AS freight_total
      FROM stg_items GROUP BY order_id
    ), payment_agg AS (
      SELECT order_id, SUM(payment_value) AS payment_total,
        COUNT(*) AS payment_rows
      FROM stg_payments GROUP BY order_id
    ), review_agg AS (
      SELECT order_id, AVG(review_score) AS review_score,
        COUNT(review_score) AS review_count
      FROM stg_reviews GROUP BY order_id
    )
    SELECT o.order_id, o.customer_id, c.customer_unique_id, c.customer_state, c.customer_city,
      o.order_status, o.order_purchase_timestamp, o.order_delivered_customer_date,
      o.order_estimated_delivery_date, i.item_count,
      ROUND(COALESCE(i.item_total,0),2) item_total,
      ROUND(COALESCE(i.freight_total,0),2) freight_total,
      ROUND(COALESCE(p.payment_total,0),2) payment_total,
      p.payment_rows, r.review_score, r.review_count,
      CASE WHEN o.order_delivered_customer_date IS NOT NULL AND o.order_estimated_delivery_date IS NOT NULL
        THEN CAST(julianday(o.order_delivered_customer_date)-julianday(o.order_estimated_delivery_date) AS REAL)
        ELSE NULL END delivery_delay_days
    FROM stg_orders o
    LEFT JOIN stg_customers c ON o.customer_id=c.customer_id
    LEFT JOIN item_agg i ON o.order_id=i.order_id
    LEFT JOIN payment_agg p ON o.order_id=p.order_id
    LEFT JOIN review_agg r ON o.order_id=r.order_id;
    CREATE UNIQUE INDEX ux_mart_orders_order_id ON mart_orders(order_id);
    CREATE INDEX ix_mart_purchase_date ON mart_orders(order_purchase_timestamp);
    COMMIT;
    """)
    LOG.info("Mart complete: %s rows", conn.execute("SELECT COUNT(*) FROM mart_orders").fetchone()[0])

def run_quality_checks(conn, sql_dir: Path, output_dir: Path, fail_on_critical=True):
    import csv, json
    output_dir.mkdir(parents=True, exist_ok=True)
    results=[]
    for path in sorted(sql_dir.glob("*.sql")):
        sql=path.read_text(encoding="utf-8")
        rows=conn.execute(sql).fetchall()
        count=len(rows)
        critical=path.stem in {"qc_order_id_integrity","qc_delivery_chronology","qc_customer_match","qc_review_score"}
        results.append({"check":path.stem,"severity":"CRITICAL" if critical else "WARNING",
                        "failing_rows":count,"sample_records":[list(r) for r in rows[:10]],
                        "disposition":("flagged; raw/staging retained" if count else "passed; no action")})
        LOG.info("Quality check %s: %d failing rows (%s)",path.stem,count,"CRITICAL" if critical else "WARNING")
        if count and critical and fail_on_critical:
            # Continue to collect all checks, then fail as a group.
            pass
    with (output_dir/"quality_results.json").open("w",encoding="utf-8") as f: json.dump(results,f,indent=2,default=str)
    with (output_dir/"quality_results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["check","severity","failing_rows","disposition"]); w.writeheader()
        for r in results: w.writerow({k:r[k] for k in w.fieldnames})
    critical_failures=[r for r in results if r["severity"]=="CRITICAL" and r["failing_rows"]]
    if critical_failures and fail_on_critical:
        raise RuntimeError("Critical data-quality checks failed: "+", ".join(f"{r['check']}={r['failing_rows']}" for r in critical_failures))
    return results

def main():
    configure_logging()
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",type=Path,default=DEFAULT_DATA)
    ap.add_argument("--db",type=Path,default=DEFAULT_DB)
    ap.add_argument("--skip-quality-fail",action="store_true",help="Report critical failures without exiting nonzero (diagnostic only)")
    args=ap.parse_args()
    args.db.parent.mkdir(parents=True,exist_ok=True)
    try:
        with sqlite3.connect(args.db) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN")
            load_raw(conn,args.data_dir)
            create_staging(conn)
            create_mart(conn)
            conn.commit()
            # Quality results are produced after table transaction; critical checks alarm clearly.
            run_quality_checks(conn,ROOT/"sql"/"quality",ROOT/"outputs",not args.skip_quality_fail)
        LOG.info("Pipeline completed successfully")
    except Exception as exc:
        LOG.exception("Pipeline failed: %s",exc)
        sys.exit(1)
if __name__=="__main__": main()
