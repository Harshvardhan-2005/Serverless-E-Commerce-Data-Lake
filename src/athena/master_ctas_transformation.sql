-- =============================================================================
-- Enterprise Serverless Data Lake - Athena Master CTAS Transformation Query
-- Author: Gauransh (23/IT/057)
--
-- Target: Creates a Snappy-compressed Apache Parquet table in the S3 Curated Zone
-- Features:
--   1. Imputation: Missing city categories are imputed via COALESCE(NULLIF(c.city, ''), 'Unknown City').
--   2. Fraud Feature Engineering: Billing vs Shipping address mismatch check -> fraud_flag (1 or 0).
--   3. Orphan Record Filtering: Removes invalid guest traffic -> WHERE e.user_id != 'GUEST'.
--   4. Type Casting: Normalizes XML prices -> CAST(p.price AS DOUBLE).
-- =============================================================================

-- Drop existing master table metadata before execution
DROP TABLE IF EXISTS ecommerce_datalake_db.ecommerce_analytics_master;

-- Create Curated Master Table
CREATE TABLE ecommerce_datalake_db.ecommerce_analytics_master
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location = 's3://cws-ecommerce-datalake-sd-9921/curated-zone/'
) AS
SELECT
    e.event_id,
    e.timestamp AS event_timestamp,
    e.user_id,
    COALESCE(NULLIF(c.full_name, ''), 'Unknown Customer') AS customer_name,
    c.age AS customer_age,
    
    -- 1. Category Imputation for Dirty Data (~10% missing city in CSV)
    COALESCE(NULLIF(c.city, ''), 'Unknown City') AS customer_city,
    
    c.state AS customer_state,
    c.shipping_address,
    p.product_id,
    p.category AS product_category,
    
    -- 2. Strict Type Casting for Clean XML Prices
    CAST(p.price AS DOUBLE) AS product_price,
    
    e.event_type,
    r.order_id,
    r.payment_method,
    r.promo_code,
    r.billing_address,
    
    -- 3. Live Fraud Flag Feature Engineering (~15% address mismatches in PDF receipts)
    CASE 
        WHEN c.shipping_address != r.billing_address THEN 1 
        ELSE 0 
    END AS fraud_flag

FROM processed_zone.events e
LEFT JOIN processed_zone.customers c ON e.user_id = c.user_id
LEFT JOIN processed_zone.products p ON e.product_id = p.product_id
LEFT JOIN processed_zone.receipts r ON e.user_id = r.customer_id AND e.product_id = r.product_id

-- 4. Filtering Orphaned Guest Records (~5% in JSON clickstream)
WHERE e.user_id != 'GUEST';
