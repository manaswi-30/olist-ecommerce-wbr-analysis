"""Fast validation tests; run with: python -m unittest discover -s tests -v"""
import sqlite3, tempfile, unittest, subprocess
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pipeline

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=ROOT/'data'/'olist_wbr.sqlite'
        if not cls.db.exists():
            raise unittest.SkipTest("Run pipeline.py with the Olist dataset first")
    def test_mart_one_row_per_order(self):
        with sqlite3.connect(self.db) as c:
            total, distinct = c.execute("SELECT COUNT(*),COUNT(DISTINCT order_id) FROM mart_orders").fetchone()
            source = c.execute("SELECT COUNT(DISTINCT order_id) FROM stg_orders").fetchone()[0]
        self.assertEqual(total,distinct)
        self.assertEqual(total,source)
    def test_item_payment_aggregates_not_join_fanned_out(self):
        with sqlite3.connect(self.db) as c:
            order_id, expected = c.execute("SELECT order_id,SUM(price) FROM stg_items GROUP BY order_id ORDER BY order_id LIMIT 1").fetchone()
            actual = c.execute("SELECT item_total FROM mart_orders WHERE order_id=?",(order_id,)).fetchone()[0]
            self.assertAlmostEqual(expected,actual,places=2)
            order_id, expected_pay = c.execute("SELECT order_id,SUM(payment_value) FROM stg_payments GROUP BY order_id ORDER BY order_id LIMIT 1").fetchone()
            actual_pay = c.execute("SELECT payment_total FROM mart_orders WHERE order_id=?",(order_id,)).fetchone()[0]
            self.assertAlmostEqual(expected_pay,actual_pay,places=2)
    def test_quality_checks_exist_and_execute(self):
        with sqlite3.connect(self.db) as c:
            results=pipeline.run_quality_checks(c,ROOT/'sql'/'quality',Path(tempfile.mkdtemp()),False)
        self.assertGreaterEqual(len(results),5)
    def test_critical_check_failure_raises(self):
        with sqlite3.connect(self.db) as c:
            c.execute("BEGIN")
            c.execute("UPDATE stg_reviews SET review_score=9 WHERE rowid=(SELECT MIN(rowid) FROM stg_reviews)")
            with self.assertRaises(RuntimeError):
                pipeline.run_quality_checks(c,ROOT/'sql'/'quality',Path(tempfile.mkdtemp()),True)
            c.rollback()

    def test_all_analysis_sql_executes(self):
        with sqlite3.connect(self.db) as c:
            files=sorted((ROOT/'sql'/'analysis').glob('*.sql'))
            self.assertEqual(len(files),5)
            for path in files:
                c.execute(path.read_text()).fetchall()
    def test_pipeline_is_idempotent(self):
        def snapshot():
            with sqlite3.connect(self.db) as c:
                return c.execute("SELECT COUNT(*),COUNT(DISTINCT order_id),ROUND(SUM(item_total),2),ROUND(SUM(payment_total),2) FROM mart_orders").fetchone()
        before=snapshot()
        raw=ROOT/'data'/'raw'
        if not raw.exists() or not (raw/'olist_orders_dataset.csv').exists():
            self.skipTest("Olist CSVs not present; download and extract dataset first")
        subprocess.run([sys.executable,str(ROOT/'pipeline.py'),'--skip-quality-fail'],cwd=ROOT,check=True,capture_output=True,text=True,timeout=45)
        self.assertEqual(before,snapshot())

    def test_missing_file_error_is_clear(self):
        with tempfile.TemporaryDirectory() as td, sqlite3.connect(":memory:") as c:
            with self.assertRaisesRegex(FileNotFoundError,"Required input file is missing"):
                pipeline.load_raw(c,Path(td))

if __name__=="__main__": unittest.main()
