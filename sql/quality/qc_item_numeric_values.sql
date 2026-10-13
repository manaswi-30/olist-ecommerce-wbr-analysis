-- Warning: item records with invalid/missing or negative price/freight.
SELECT order_id, order_item_id, price, freight_value FROM stg_items
WHERE price IS NULL OR freight_value IS NULL OR price < 0 OR freight_value < 0;
