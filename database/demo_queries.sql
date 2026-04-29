-- SmartRetail-Sync - PostgreSQL demo queries
-- Run these queries in pgAdmin Query Tool.

-- 1. List tables and views
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 2. Count loaded data
SELECT 'dim_products' AS object_name, COUNT(*) AS row_count FROM dim_products
UNION ALL
SELECT 'dim_stores', COUNT(*) FROM dim_stores
UNION ALL
SELECT 'dim_inventory', COUNT(*) FROM dim_inventory
UNION ALL
SELECT 'fact_sales', COUNT(*) FROM fact_sales;

-- 3. Products
SELECT product_code, product_name, category, subcategory
FROM dim_products
ORDER BY product_code;

-- 4. Sales summary view
SELECT full_date, store_name, region, product_name,
       total_quantity, total_revenue, transaction_count
FROM vw_sales_summary
ORDER BY full_date DESC, product_name;

-- 5. Inventory alerts view
SELECT product_code, product_name, store_name, region,
       stock_level, reorder_point, stock_status
FROM vw_inventory_alerts
WHERE stock_status <> 'NORMAL'
ORDER BY stock_level ASC;

-- 6. Full sales fact table with dimensions
SELECT f.sales_id,
       d.full_date,
       s.store_code,
       s.store_name,
       p.product_code,
       p.product_name,
       f.quantity_sold,
       f.net_amount,
       f.transaction_id
FROM fact_sales f
JOIN dim_dates d ON f.date_id = d.date_id
JOIN dim_stores s ON f.store_id = s.store_id
JOIN dim_products p ON f.product_id = p.product_id
ORDER BY f.sales_id DESC;

-- 7. Power BI style analytical query
SELECT d.year,
       d.month,
       d.month_name,
       s.region,
       p.category,
       p.product_name,
       SUM(f.quantity_sold) AS total_quantity,
       SUM(f.net_amount) AS total_revenue,
       COUNT(DISTINCT f.transaction_id) AS transaction_count
FROM fact_sales f
JOIN dim_dates d ON f.date_id = d.date_id
JOIN dim_stores s ON f.store_id = s.store_id
JOIN dim_products p ON f.product_id = p.product_id
GROUP BY d.year, d.month, d.month_name, s.region, p.category, p.product_name
ORDER BY d.year DESC, d.month DESC, total_revenue DESC;

