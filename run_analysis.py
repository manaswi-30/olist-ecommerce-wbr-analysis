"""Execute saved Part C SQL with SQLite and produce four matplotlib charts."""
from pathlib import Path
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'olist_wbr.sqlite'
OUT=ROOT/'outputs'; CHARTS=OUT/'charts'; CHARTS.mkdir(parents=True,exist_ok=True)
def main():
    with sqlite3.connect(DB) as conn:
        results={}
        for path in sorted((ROOT/'sql'/'analysis').glob('*.sql')):
            df=pd.read_sql_query(path.read_text(encoding='utf-8'),conn)
            df.to_csv(OUT/f'{path.stem}_results.csv',index=False)
            results[path.stem]=df
    # 1. Monthly gross item revenue
    df=results['01_monthly_revenue_growth']
    fig,ax=plt.subplots(figsize=(9,4.6)); ax.plot(df['month'],df['revenue'],marker='o',linewidth=1.8)
    ax.set_title('Monthly Gross Item Revenue (excluding freight)'); ax.set_xlabel('Purchase month'); ax.set_ylabel('Revenue (BRL)')
    ax.tick_params(axis='x',rotation=55); ax.grid(True,alpha=.25); fig.tight_layout(); fig.savefig(CHARTS/'monthly_revenue.png',dpi=160); plt.close(fig)
    # 2. Daily orders, latest 90 days in observed data
    df=results['03_rolling_7day_orders'].tail(90)
    fig,ax=plt.subplots(figsize=(9,4.6)); ax.bar(df['day'],df['order_count'],label='Daily orders',alpha=.55)
    ax.plot(df['day'],df['rolling_7day_avg'],label='7-day rolling average',linewidth=2)
    ax.set_title('Daily Orders and 7-Day Rolling Average (last 90 observed dates)'); ax.set_xlabel('Date'); ax.set_ylabel('Orders per day')
    ax.tick_params(axis='x',rotation=55); ax.legend(); ax.grid(True,axis='y',alpha=.25); fig.tight_layout(); fig.savefig(CHARTS/'daily_orders_rolling.png',dpi=160); plt.close(fig)
    # 3. Delivery experience by review score
    df=results['05_delivery_delay_vs_review']
    fig,ax=plt.subplots(figsize=(8,4.6)); ax.bar(df['review_score'].astype(str),df['pct_delivered_late'])
    ax.set_title('Share Delivered After Estimated Date by Review Score'); ax.set_xlabel('Review score (1 = lowest, 5 = highest)'); ax.set_ylabel('Delivered late (%)')
    ax.grid(True,axis='y',alpha=.25); fig.tight_layout(); fig.savefig(CHARTS/'late_delivery_by_review.png',dpi=160); plt.close(fig)
    # 4. Repeat purchase rate
    df=results['04_repeat_purchase_rate'].iloc[0]
    fig,ax=plt.subplots(figsize=(6.5,4.6)); labels=['One-time customers','Repeat customers']
    vals=[int(df['identified_customers']-df['repeat_customers']),int(df['repeat_customers'])]
    ax.bar(labels,vals); ax.set_title('Identified Customers by Purchase Frequency'); ax.set_ylabel('Distinct customer_unique_id count')
    ax.grid(True,axis='y',alpha=.25); fig.tight_layout(); fig.savefig(CHARTS/'repeat_customers.png',dpi=160); plt.close(fig)
    print('Executed 5 SQL analyses; wrote result CSVs and 4 charts.')
if __name__=='__main__': main()
