# Architecture Détaillée - SmartRetail-Sync

## 🏗️ Vue d'ensemble

SmartRetail-Sync implémente une architecture **microservices** avec une **couche de données analytiques** optimisée pour Power BI.

---

## 1️⃣ Couche Présentation (API)

### FastAPI (`backend/src/main.py`)

**Responsabilités:**
- Recevoir les requêtes HTTP(S) des clients
- Valider les données entrantes avec Pydantic
- Orchestrer la logique métier
- Retourner les réponses structurées

**Points clés:**
```python
# 1. CORS configuré pour Power BI
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://app.powerbi.com",
]

# 2. Exception handlers personnalisés
- SmartRetailException → JSON structuré
- RequestValidationError → Détails de validation
- Exception générale → Message sécurisé

# 3. Lifecycle management (startup/shutdown)
async def lifespan(app):
    # Startup: Initialize DB, test connection
    # Shutdown: Close connections, cleanup
```

### Routers

#### `/sales` (`sales.py`)
```python
POST /api/v1/sales/upload-sale
- Endpoint principal pour l'ingestion de ventes
- Valide store, products, montants
- Insère dans fact_sales et met à jour inventory
- Retourne transaction_id et sales_ids

GET /api/v1/sales/summary
- Agrégations par date, store, produit
- Filtres optionnels (store, région, dates)
- Source: Vue vw_sales_summary
```

#### `/inventory` (`inventory.py`)
```python
GET /api/v1/inventory/low-stock
- Récupère les items en stock critique
- Source: Vue vw_inventory_alerts
- Triés par priorité (stock_level ASC)

PUT /api/v1/inventory/update
- Met à jour les niveaux de stock
- Valide product et store
- Met à jour reorder_point

GET /api/v1/inventory/by-product/{product_code}
- Inventaire d'un produit tous magasins
```

---

## 2️⃣ Couche Métier (Services)

### SalesService (`services/sales_service.py`)

**Responsabilités:**
1. **Validation** : Store & product existence
2. **Enrichissement** : Lookup date_id, product_id, store_id
3. **Calcul** : net_amount = total - discount + tax
4. **Insertion** : Transactions atomiques
5. **Mise à jour** : Inventory stock level

**Flux:**
```
UploadSaleRequest
    ↓
Validate Store (dim_stores)
    ↓
Validate Unique Transaction ID
    ↓
Get/Create Date (dim_dates)
    ↓
For each Item:
    ├─ Get Product (dim_products)
    ├─ Get/Create Inventory (dim_inventory)
    ├─ Validate Calculations
    ├─ Insert Sale (fact_sales)
    └─ Update Stock (dim_inventory.stock_level -=)
    ↓
Commit Transaction
    ↓
Return Response with sales_ids
```

**Gestion des Erreurs:**
```python
# Custom exceptions avec status codes
NotFoundError(404) → Store/Product pas trouvé
ValidationError(400) → Données invalides
DatabaseError(500) → Erreur BD avec rollback
DuplicateError(409) → Transaction ID déjà existe
```

---

## 3️⃣ Couche Données (Database)

### PostgreSQL Star Schema

#### Architecture Star
```
FAIT CENTRAL (fact_sales)
    ├─ Clés étrangères vers 4 dimensions
    ├─ Mesures (quantities, montants)
    └─ Traçabilité (timestamps, cashier_id)

DIMENSIONS
    ├─ dim_dates (365+ jours)
    ├─ dim_products (codes produits)
    ├─ dim_stores (magasins/régions)
    └─ dim_inventory (stocks par product-store)
```

#### Indexes Stratégiques
```sql
-- Jointures rapides
CREATE INDEX idx_fact_sales_date_id ON fact_sales(date_id);
CREATE INDEX idx_fact_sales_product_id ON fact_sales(product_id);
CREATE INDEX idx_fact_sales_store_id ON fact_sales(store_id);

-- Time-series analysis
CREATE INDEX idx_fact_sales_timestamp ON fact_sales(sales_timestamp DESC);

-- Composite pour magasin-produit analysis
CREATE INDEX idx_fact_sales_store_product 
ON fact_sales(store_id, product_id, sales_timestamp);

-- Lookups
CREATE INDEX idx_dim_products_category ON dim_products(category);
CREATE INDEX idx_dim_stores_region ON dim_stores(region);
CREATE INDEX idx_dim_inventory_product_store 
ON dim_inventory(product_id, store_id);
```

#### Vues Analytiques
```sql
-- vw_sales_summary: Rapports par jour/magasin/produit
-- Source pour Power BI dashboards
-- Agrégation: SUM(quantity), SUM(revenue), COUNT(transactions)

-- vw_inventory_alerts: Items en stock critique
-- Source pour notifications de réapprovisionnement
-- États: NORMAL, LOW_STOCK, REORDER_NEEDED
```

#### Contraintes d'Intégrité
```sql
-- Clés étrangères (referential integrity)
FOREIGN KEY (date_id) REFERENCES dim_dates
FOREIGN KEY (product_id) REFERENCES dim_products
FOREIGN KEY (store_id) REFERENCES dim_stores

-- Contraintes de domaine
CHECK (quantity_sold > 0)
CHECK (unit_price > 0)
CHECK (stock_level >= 0)
CHECK (net_amount = total - discount + tax)

-- Unicité
UNIQUE(product_id, store_id)  -- 1 inventory per product-store
UNIQUE(transaction_id)         -- No duplicate transactions
```

---

## 4️⃣ Couche Configuration & Sécurité

### Settings Management (`config/settings.py`)

**Stratégie d'environnement:**
```python
# LOCAL (development)
ENVIRONMENT = "local"
→ Load from .env file
→ Credentials en clair (dev only!)

# PRODUCTION (Azure)
ENVIRONMENT = "production"
→ Load from Azure Key Vault
→ DefaultAzureCredential (Managed Identity)
```

### Azure Key Vault Integration (`config/keyvault.py`)

**Credential Priority:**
```
1. DefaultAzureCredential (Managed Identity via App Service)
   └─ No credentials needed, automatically discovered
   
2. ClientSecretCredential (Service Principal)
   └─ AZURE_CLIENT_ID + AZURE_CLIENT_SECRET
   
3. Azure CLI credentials
   └─ Via 'az login'
```

**Secrets Stockés:**
```
Key Vault: kv-smartretail-{random}

├─ db-host: postgresql-server.postgres.database.azure.com
├─ db-user: dbadmin
└─ db-password: (random generated)
```

**Avantages:**
- ✅ Zero hardcoded credentials
- ✅ Automatic credential rotation
- ✅ Audit trail in Azure
- ✅ RBAC control (who accesses what)

---

## 5️⃣ Couche Base de Données (Connection Management)

### DatabaseManager (`services/database.py`)

**Connexion Asynchrone (FastAPI):**
```python
# Async Engine avec asyncpg
async_db_url = "postgresql+asyncpg://user:pass@host/db"

engine = create_async_engine(
    async_db_url,
    pool_size=20,           # Connexions actives
    max_overflow=40,        # Connexions supplémentaires
    pool_timeout=30,        # Timeout pour obtenir connexion
    pool_recycle=3600,      # Recycle toutes les heures
    pool_pre_ping=True,     # Test connexion avant usage
)
```

**Context Manager pour Sessions:**
```python
async with db_manager.get_session() as session:
    # Commit automatique si pas d'erreur
    # Rollback automatique si exception
    # Close automatique
    result = await session.execute(query)
```

**Connection Pooling Synchrone (Batch):**
```python
# Pour opérations batch, scripts init
pool = DatabaseManager.create_sync_connection_pool(
    min_connections=5,
    max_connections=20
)
```

---

## 6️⃣ Validation & Modèles (Pydantic)

### Schemas (`models/schemas.py`)

**Validation à l'entrée:**
```python
class SaleItemRequest(BaseModel):
    product_code: str = Field(..., min_length=1, max_length=50)
    quantity_sold: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., decimal_places=2, gt=0)
    discount_amount: Decimal = Field(default=0, decimal_places=2, ge=0)
    
    @validator('discount_amount')
    def validate_discount(cls, v, values):
        if v > values['unit_price'] * 0.5:
            raise ValueError('Max discount 50%')
        return v
```

**Validation à la sortie:**
```python
class UploadSaleResponse(BaseModel):
    success: bool
    message: str
    sales_ids: List[int]
    total_amount: Decimal
    
    # JSON encoding pour Decimal
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }
```

**Avantages:**
- ✅ Auto-validation des types
- ✅ Custom validators
- ✅ Documentation Swagger automatique
- ✅ Sérialisation JSON automatique

---

## 7️⃣ Gestion des Erreurs

### Custom Exceptions (`utils/errors.py`)

```python
class SmartRetailException(Exception):
    # Base class avec:
    # - message
    # - error_code
    # - status_code
    # - details

class NotFoundError(SmartRetailException)      # 404
class ValidationError(SmartRetailException)    # 400
class DatabaseError(SmartRetailException)      # 500
class KeyVaultError(SmartRetailException)      # 500
```

### Exception Handlers (main.py)

```python
@app.exception_handler(SmartRetailException)
async def handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )
```

---

## 8️⃣ Logging & Monitoring

### Structured Logging (`utils/logger.py`)

```python
setup_logging(
    log_level="INFO",
    log_file="logs/smartretail_sync.log"
)

# Formatage:
# 2024-04-29 14:23:45 - sales_service - INFO - Inserted sale 12345
```

### Health Checks

```python
GET /health
Response: {
    "status": "healthy|degraded|unhealthy",
    "database": "connected|disconnected",
    "version": "1.0.0",
    "environment": "production"
}
```

---

## 9️⃣ Déploiement Automatisé

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/src ./src
EXPOSE 8000
HEALTHCHECK --interval=30s ...
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

### Docker Compose (Local)

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: smartretail_user
      POSTGRES_PASSWORD: smartretail_password
      POSTGRES_DB: smartretail_db
    volumes:
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      
  backend:
    build: .
    environment:
      ENVIRONMENT: local
      DB_HOST: postgres
    depends_on:
      postgres:
        condition: service_healthy
```

### Azure Infrastructure Script

```powershell
# setup.ps1 crée:
├─ Resource Group
├─ Azure Key Vault
├─ PostgreSQL Flexible Server
├─ App Service Plan
├─ App Service
├─ Managed Identity
└─ RBAC Policies
```

---

## 🔟 Flux de Données Complet

### Scénario: Upload Sale

```
1. Client API (POS System)
   │
   └─► POST /api/v1/sales/upload-sale
       {store_code, transaction_id, items[]}
       │
       ├─ Pydantic validation
       │
   ├─► FastAPI routing → sales router
       │
       ├─► SalesService.upload_sale()
           │
           ├─ Query: SELECT store_id FROM dim_stores
           │
           ├─ Query: SELECT date_id FROM dim_dates OR INSERT
           │
           ├─ Query: SELECT product_id FROM dim_products
           │
           ├─ Query: SELECT inventory_id FROM dim_inventory
           │          OR INSERT with default values
           │
           ├─ INSERT INTO fact_sales
           │   (date_id, product_id, store_id, inventory_id,
           │    quantity_sold, unit_price, total_amount, ...)
           │
           ├─ UPDATE dim_inventory
           │  SET stock_level = stock_level - quantity_sold
           │
           ├─ COMMIT transaction
           │
       ├─► Return: UploadSaleResponse
           {success: true, sales_ids: [123, 124], total_amount: 2000.00}

2. PowerBI
   ├─ SELECT FROM vw_sales_summary
   ├─ Refresh dashboard automatically
   └─ Show: Revenue, quantities, trends
```

---

## 🎯 Décisions Architecturales

### Pourquoi Star Schema?
✅ Performance optimale pour OLAP (analytique)
✅ Dimidité et normalisation (jointures simples)
✅ Scalabilité pour millions de transactions

### Pourquoi FastAPI?
✅ Async par défaut (haute concurrence)
✅ Validation automatique (Pydantic)
✅ Documentation Swagger gratuite
✅ Performance (bench#1 vs Django, Flask)

### Pourquoi PostgreSQL?
✅ Robustesse (ACID, constraints)
✅ Scalabilité verticale/horizontale
✅ Flexible Server managé sur Azure
✅ Écosystème outils

### Pourquoi Azure?
✅ Key Vault pour secrets
✅ Managed Identity (zero credentials)
✅ App Service (autoscaling)
✅ Monitoring & logging intégrés

---

**Document mis à jour:** 2024-04-29
**Version:** 1.0.0
