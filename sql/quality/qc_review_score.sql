-- Critical: raw review scores should be within the documented 1..5 scale.
SELECT order_id, review_score FROM stg_reviews
WHERE review_score IS NULL OR review_score NOT BETWEEN 1 AND 5;
