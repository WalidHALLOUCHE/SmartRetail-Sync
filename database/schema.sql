-- ============================================
-- SmartRetail-Sync: Star Schema SQL
-- PostgreSQL Database Schema
-- Fait: fact_sales avec 4 dimensions
-- ============================================

-- ============================================
-- 1. DIMENSION TABLES
-- ============================================

-- dim_dates: Table des dimensions temporelles
CREATE TABLE dim_dates (
    date_id SERIAL PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_of_week INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- dim_products: Table des dimensions produits
CREATE TABLE dim_products (
    product_id SERIAL PRIMARY KEY,
    product_code VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    price_range VARCHAR(50),
    supplier_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_product_code_not_empty CHECK (product_code != '')
);

-- dim_stores: Table des dimensions magasins
CREATE TABLE dim_stores (
    store_id SERIAL PRIMARY KEY,
    store_code VARCHAR(50) NOT NULL UNIQUE,
    store_name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    store_type VARCHAR(50),
    manager_name VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_store_code_not_empty CHECK (store_code != '')
);

-- dim_inventory: Table des dimensions inventaire (état des stocks)
CREATE TABLE dim_inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES dim_products(product_id) ON DELETE CASCADE,
    store_id INT NOT NULL REFERENCES dim_stores(store_id) ON DELETE CASCADE,
    stock_level INT NOT NULL DEFAULT 0,
    reorder_point INT DEFAULT 0,
    reorder_quantity INT DEFAULT 0,
    last_restock_date DATE,
    warehouse_location VARCHAR(100),
    shelf_location VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stock_level_positive CHECK (stock_level >= 0),
    CONSTRAINT uq_product_store_inventory UNIQUE(product_id, store_id)
);

-- ============================================
-- 2. FACT TABLE
-- ============================================

-- fact_sales: Table des ventes centrales
CREATE TABLE fact_sales (
    sales_id BIGSERIAL PRIMARY KEY,
    date_id INT NOT NULL REFERENCES dim_dates(date_id),
    product_id INT NOT NULL REFERENCES dim_products(product_id),
    store_id INT NOT NULL REFERENCES dim_stores(store_id),
    inventory_id INT NOT NULL REFERENCES dim_inventory(inventory_id),
    
    -- Faits (mesures)
    quantity_sold INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(10, 2) DEFAULT 0,
    net_amount DECIMAL(12, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) DEFAULT 0,
    
    -- Traçabilité
    sales_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cashier_id VARCHAR(50),
    payment_method VARCHAR(50),
    transaction_id VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Contraintes d'intégrité
    CONSTRAINT chk_quantity_positive CHECK (quantity_sold > 0),
    CONSTRAINT chk_unit_price_positive CHECK (unit_price > 0),
    CONSTRAINT chk_total_amount_positive CHECK (total_amount >= 0),
    CONSTRAINT chk_net_calculation CHECK (net_amount = (total_amount - discount_amount + tax_amount))
);

-- ============================================
-- 3. INDEXES pour optimisation de performance
-- ============================================

-- Indexes sur fact_sales pour les jointures
CREATE INDEX idx_fact_sales_date_id ON fact_sales(date_id);
CREATE INDEX idx_fact_sales_product_id ON fact_sales(product_id);
CREATE INDEX idx_fact_sales_store_id ON fact_sales(store_id);
CREATE INDEX idx_fact_sales_inventory_id ON fact_sales(inventory_id);

-- Index sur sales_timestamp pour les agrégations temporelles
CREATE INDEX idx_fact_sales_timestamp ON fact_sales(sales_timestamp DESC);

-- Index sur transaction_id pour détecter rapidement les ré-imports
CREATE INDEX idx_fact_sales_transaction_id ON fact_sales(transaction_id);

-- Index composé pour analyse store-product
CREATE INDEX idx_fact_sales_store_product ON fact_sales(store_id, product_id, sales_timestamp);

-- Index sur dim_tables pour lookups
CREATE INDEX idx_dim_products_category ON dim_products(category);
CREATE INDEX idx_dim_stores_region ON dim_stores(region);
CREATE INDEX idx_dim_inventory_product_store ON dim_inventory(product_id, store_id);

-- ============================================
-- 4. VUE ANALYTIQUE
-- ============================================

-- Vue pour les rapports de ventes par jour et magasin
CREATE VIEW vw_sales_summary AS
SELECT 
    d.full_date,
    s.store_name,
    s.region,
    p.product_name,
    p.category,
    SUM(f.quantity_sold) AS total_quantity,
    SUM(f.net_amount) AS total_revenue,
    COUNT(DISTINCT f.sales_id) AS transaction_count,
    AVG(f.net_amount) AS avg_transaction_value
FROM fact_sales f
INNER JOIN dim_dates d ON f.date_id = d.date_id
INNER JOIN dim_stores s ON f.store_id = s.store_id
INNER JOIN dim_products p ON f.product_id = p.product_id
GROUP BY d.full_date, s.store_name, s.region, p.product_name, p.category
ORDER BY d.full_date DESC, s.store_name;

-- Vue pour le suivi des stocks critiques
CREATE VIEW vw_inventory_alerts AS
SELECT 
    i.inventory_id,
    p.product_code,
    p.product_name,
    s.store_name,
    s.region,
    i.stock_level,
    i.reorder_point,
    CASE 
        WHEN i.stock_level <= i.reorder_point THEN 'REORDER_NEEDED'
        WHEN i.stock_level <= (i.reorder_point * 1.5) THEN 'LOW_STOCK'
        ELSE 'NORMAL'
    END AS stock_status
FROM dim_inventory i
INNER JOIN dim_products p ON i.product_id = p.product_id
INNER JOIN dim_stores s ON i.store_id = s.store_id
WHERE p.is_active = TRUE AND s.is_active = TRUE
ORDER BY i.stock_level ASC;

-- ============================================
-- 5. FONCTIONS UTILITAIRES
-- ============================================

-- Fonction pour mettre à jour l'updated_at automatiquement
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
CREATE TRIGGER trg_dim_products_updated
BEFORE UPDATE ON dim_products
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_dim_stores_updated
BEFORE UPDATE ON dim_stores
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_dim_inventory_updated
BEFORE UPDATE ON dim_inventory
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_fact_sales_updated
BEFORE UPDATE ON fact_sales
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================
-- 6. DONNÉES D'EXEMPLE
-- ============================================

-- Insérer les dates (exemple: 365 jours)
INSERT INTO dim_dates (full_date, day_of_week, day_name, month, month_name, quarter, year, is_weekend)
SELECT 
    DATE('2024-01-01') + (n || ' days')::INTERVAL,
    EXTRACT(DOW FROM DATE('2024-01-01') + (n || ' days')::INTERVAL)::INT,
    TO_CHAR(DATE('2024-01-01') + (n || ' days')::INTERVAL, 'Day'),
    EXTRACT(MONTH FROM DATE('2024-01-01') + (n || ' days')::INTERVAL)::INT,
    TO_CHAR(DATE('2024-01-01') + (n || ' days')::INTERVAL, 'Month'),
    EXTRACT(QUARTER FROM DATE('2024-01-01') + (n || ' days')::INTERVAL)::INT,
    EXTRACT(YEAR FROM DATE('2024-01-01') + (n || ' days')::INTERVAL)::INT,
    EXTRACT(DOW FROM DATE('2024-01-01') + (n || ' days')::INTERVAL)::INT IN (0, 6)
FROM GENERATE_SERIES(0, 364) AS n;

-- Insérer les produits
INSERT INTO dim_products (product_code, product_name, category, subcategory, price_range, supplier_id)
VALUES 
    ('PRD001', 'Laptop Pro', 'Electronics', 'Computers', 'Premium', 1),
    ('PRD002', 'Wireless Mouse', 'Electronics', 'Accessories', 'Budget', 2),
    ('PRD003', 'USB-C Cable', 'Electronics', 'Cables', 'Budget', 2),
    ('PRD004', 'Monitor 27"', 'Electronics', 'Monitors', 'Mid-Range', 1),
    ('PRD005', 'Mechanical Keyboard', 'Electronics', 'Peripherals', 'Mid-Range', 3);

-- Insérer les magasins
INSERT INTO dim_stores (store_code, store_name, city, region, country, store_type, manager_name)
VALUES 
    ('STR001', 'Paris Central', 'Paris', 'Île-de-France', 'France', 'Flagship', 'Jean Dupont'),
    ('STR002', 'Lyon Store', 'Lyon', 'Auvergne-Rhône-Alpes', 'France', 'Standard', 'Marie Martin'),
    ('STR003', 'Marseille Center', 'Marseille', 'Provence-Alpes-Côte d''Azur', 'France', 'Express', 'Pierre Bernard'),
    ('STR004', 'Brussels Hub', 'Brussels', 'Brussels', 'Belgium', 'Flagship', 'Luc Vermeer');

-- Insérer les inventaires
INSERT INTO dim_inventory (product_id, store_id, stock_level, reorder_point, reorder_quantity, warehouse_location)
SELECT p.product_id, s.store_id, 
    FLOOR(RANDOM() * 500 + 50),
    100, 200, 'Warehouse-A'
FROM dim_products p, dim_stores s;
