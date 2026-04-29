# 🎨 SmartRetail-Sync - Bonnes Pratiques & Patterns

## Table des Matières
1. [Clean Code](#clean-code)
2. [Design Patterns](#design-patterns)
3. [Security Best Practices](#security)
4. [Performance Optimization](#performance)
5. [Error Handling](#error-handling)
6. [Logging & Monitoring](#logging)

---

## 🧹 Clean Code

### Principes Implémentés

#### 1. **Single Responsibility Principle (SRP)**

```python
# ❌ MAUVAIS: Une classe fait trop
class SalesManager:
    def upload_sale(self, data):
        # Valide
        # Insert dans BD
        # Envoie email
        # Appelle API tierce
        # Logs
        # Etc...
        pass

# ✅ BON: Chaque classe un rôle
class SalesService:
    """Uniquement logique métier"""
    async def upload_sale(self, sale_data):
        # Validation + insertion
        pass

class EmailService:
    """Uniquement emails"""
    async def send_sale_notification(self, sale_id):
        pass

class ExternalAPIService:
    """Uniquement API tierce"""
    async def sync_sale(self, sale_id):
        pass
```

#### 2. **DRY (Don't Repeat Yourself)**

```python
# ❌ MAUVAIS: Code répété
class SalesRouter:
    @router.get("/sales/by-date")
    async def get_sales_by_date(self, date: str):
        if not validate_date(date):
            raise ValueError("Invalid date")
        # Query...
        
    @router.get("/sales/by-store")
    async def get_sales_by_store(self, store: str):
        if not validate_store(store):
            raise ValueError("Invalid store")
        # Query...

# ✅ BON: Validateurs réutilisables
def validate_input(value, validator_func):
    if not validator_func(value):
        raise ValueError(f"Invalid {validator_func.__name__}")
    return value

class SalesRouter:
    @router.get("/sales/by-date")
    async def get_sales_by_date(self, date: str):
        date = validate_input(date, validate_date)
        # Query...
```

#### 3. **Type Hints**

```python
# ❌ MAUVAIS: Pas de types
def process_sale(data):
    """Process sale data"""
    return db.insert(data)

# ✅ BON: Types explicites
from typing import List, Dict, Optional
from decimal import Decimal

async def process_sale(
    data: UploadSaleRequest,
    db_manager: DatabaseManager
) -> UploadSaleResponse:
    """
    Process and insert sale data.
    
    Args:
        data: Validated sale request
        db_manager: Database manager instance
        
    Returns:
        Sale response with inserted IDs
    """
    # Implementation...
    pass
```

#### 4. **Naming Conventions**

```python
# ❌ MAUVAIS: Noms peu clairs
class SalesService:
    def x(self, a, b):
        """Process data"""
        pass
    
    def calc(self, v1, v2):
        return v1 - v2

# ✅ BON: Noms descriptifs
class SalesService:
    async def calculate_net_amount(
        self,
        total_amount: Decimal,
        discount_amount: Decimal
    ) -> Decimal:
        """
        Calculate net amount after discount.
        
        Args:
            total_amount: Gross total
            discount_amount: Discount applied
            
        Returns:
            Net amount (total - discount)
        """
        return total_amount - discount_amount
```

---

## 🏗️ Design Patterns

### 1. **Service Layer Pattern**

```python
# Séparation claire des responsabilités
#
# Router → Service → Database
# ├─ Requests/Responses
# ├─ Business logic
# └─ SQL queries

# router/sales.py
@router.post("/upload-sale")
async def upload_sale(
    sale_data: UploadSaleRequest,
    service: SalesService = Depends()
) -> UploadSaleResponse:
    """API endpoint"""
    return await service.upload_sale(sale_data)

# services/sales_service.py
class SalesService:
    """Business logic"""
    async def upload_sale(self, sale_data: UploadSaleRequest):
        # Validate
        # Process
        # Persist
        pass

# models/schemas.py
class UploadSaleRequest(BaseModel):
    """Request validation"""
    store_code: str
    items: List[SaleItemRequest]
```

### 2. **Factory Pattern**

```python
# Création flexible de services
from enum import Enum

class DatabaseType(Enum):
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"

class DatabaseFactory:
    @staticmethod
    def create_manager(db_type: DatabaseType) -> DatabaseManager:
        if db_type == DatabaseType.POSTGRESQL:
            return PostgresManager()
        elif db_type == DatabaseType.SQLITE:
            return SQLiteManager()
        else:
            raise ValueError(f"Unknown DB type: {db_type}")

# Usage
db_manager = DatabaseFactory.create_manager(DatabaseType.POSTGRESQL)
```

### 3. **Repository Pattern**

```python
# Abstraction de l'accès aux données
from abc import ABC, abstractmethod

class SalesRepository(ABC):
    @abstractmethod
    async def insert_sale(self, sale: SaleData) -> int:
        pass
    
    @abstractmethod
    async def get_sales(self, filters: Dict) -> List[SaleData]:
        pass

class PostgresSalesRepository(SalesRepository):
    """Implémentation PostgreSQL"""
    async def insert_sale(self, sale: SaleData) -> int:
        # PostgreSQL-specific logic
        pass

class SQLiteSalesRepository(SalesRepository):
    """Implémentation SQLite"""
    async def insert_sale(self, sale: SaleData) -> int:
        # SQLite-specific logic
        pass
```

### 4. **Dependency Injection**

```python
# Couplage faible via injection
class SalesService:
    def __init__(
        self,
        db_manager: DatabaseManager,
        logger: logging.Logger,
        kv_manager: KeyVaultManager
    ):
        """Dépendances injectées"""
        self.db = db_manager
        self.logger = logger
        self.kv = kv_manager
    
    async def upload_sale(self, data: UploadSaleRequest):
        # Services fournis via constructeur
        # Facile à tester (mock les dépendances)
        pass

# FastAPI auto-injection
@router.post("/upload-sale")
async def upload_sale(
    data: UploadSaleRequest,
    service: SalesService = Depends(get_sales_service)
):
    """Service fourni par FastAPI"""
    pass
```

---

## 🔐 Security

### 1. **Secrets Management**

```python
# ❌ MAUVAIS: Secrets hardcodés
DATABASE_URL = "postgresql://user:password@localhost/db"
API_KEY = "sk_live_51234567890"

# ✅ BON: Depuis configuration
class Settings(BaseSettings):
    DB_HOST: Optional[str] = None
    DB_PASSWORD: Optional[str] = None  # Vient de .env ou Key Vault
    
    class Config:
        env_file = ".env"

# Production: Load depuis Azure Key Vault
if settings.ENVIRONMENT == "production":
    credentials = AzureKeyVaultManager.get_credentials_from_keyvault(
        vault_url=settings.AZURE_KEYVAULT_URL
    )
    settings.DB_HOST = credentials["db_host"]
```

### 2. **SQL Injection Prevention**

```python
# ❌ MAUVAIS: String interpolation
query = f"SELECT * FROM sales WHERE store_id = {store_id}"
cursor.execute(query)

# ✅ BON: Parameterized queries
query = "SELECT * FROM sales WHERE store_id = %s"
cursor.execute(query, (store_id,))
```

### 3. **Input Validation**

```python
# ❌ MAUVAIS: Pas de validation
@router.post("/upload-sale")
async def upload_sale(data: dict):
    # Assume data is valid
    db.insert(data)

# ✅ BON: Validation Pydantic
@router.post("/upload-sale")
async def upload_sale(data: UploadSaleRequest):
    # Pydantic valide automatiquement
    # - Types corrects
    # - Valeurs dans ranges
    # - Formats valides
    db.insert(data)

class UploadSaleRequest(BaseModel):
    store_code: str = Field(..., min_length=1, max_length=50)
    quantity_sold: int = Field(..., gt=0)  # Must be > 0
    unit_price: Decimal = Field(..., decimal_places=2, gt=0)
    
    @validator('unit_price')
    def validate_price(cls, v):
        if v > Decimal('999999.99'):
            raise ValueError('Price too high')
        return v
```

### 4. **CORS Configuration**

```python
# ❌ MAUVAIS: Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dangereux!
    allow_credentials=True
)

# ✅ BON: Whitelist spécifique
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://app.powerbi.com",
        "https://mycompany.com"
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=600
)
```

---

## ⚡ Performance

### 1. **Connection Pooling**

```python
# ❌ MAUVAIS: Nouvelle connexion à chaque query
def get_sales():
    conn = psycopg2.connect(...)  # Nouvelle connexion! Lent
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales")
    return cursor.fetchall()

# ✅ BON: Pool de connexions
pool = psycopg2.pool.SimpleConnectionPool(
    min_connections=5,
    max_connections=20,
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

# Réutiliser les connexions
conn = pool.getconn()
try:
    # Use connection
    pass
finally:
    pool.putconn(conn)
```

### 2. **Async Operations**

```python
# ❌ MAUVAIS: Synchrone (bloquant)
def get_sales_sync():
    # Thread attendu
    result = db.query("SELECT * FROM sales")
    return result

# Avec 10 requêtes: 10 threads x 1s = 10s total

# ✅ BON: Asynchrone (non-bloquant)
async def get_sales():
    # Event loop peut traiter autres requêtes
    result = await db.query("SELECT * FROM sales")
    return result

# Avec 10 requêtes: ~1s total!
```

### 3. **Indexing Strategy**

```sql
-- ❌ MAUVAIS: Pas d'index
SELECT * FROM fact_sales 
WHERE store_id = 5 AND date_id = 100;
-- Full table scan (lent avec millions de lignes)

-- ✅ BON: Index composite
CREATE INDEX idx_fact_sales_store_date 
ON fact_sales(store_id, date_id);
-- Index seek (très rapide)

-- Index sur clés étrangères
CREATE INDEX idx_fact_sales_date_id ON fact_sales(date_id);
CREATE INDEX idx_fact_sales_product_id ON fact_sales(product_id);

-- Index pour time-series
CREATE INDEX idx_fact_sales_timestamp 
ON fact_sales(sales_timestamp DESC);
```

### 4. **Query Optimization**

```sql
-- ❌ MAUVAIS: N+1 problem
SELECT * FROM stores;
# Python:
for store in stores:
    result = db.query(f"SELECT SUM(amount) FROM sales WHERE store_id = {store.id}")
    # Query par store = N+1 queries!

-- ✅ BON: Aggrégation en une requête
SELECT 
    s.store_id,
    s.store_name,
    SUM(fs.net_amount) as total_revenue,
    COUNT(*) as transaction_count
FROM dim_stores s
JOIN fact_sales fs ON s.store_id = fs.store_id
GROUP BY s.store_id, s.store_name;
# Une seule requête!
```

---

## 🛡️ Error Handling

### 1. **Custom Exceptions**

```python
# Hiérarchie d'exceptions
class SmartRetailException(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code

class ValidationError(SmartRetailException):
    def __init__(self, message: str):
        super().__init__(message, 400)

class NotFoundError(SmartRetailException):
    def __init__(self, message: str):
        super().__init__(message, 404)

class DatabaseError(SmartRetailException):
    def __init__(self, message: str):
        super().__init__(message, 500)
```

### 2. **Exception Handling**

```python
# ✅ BON: Handling spécifique
async def upload_sale(sale_data: UploadSaleRequest):
    try:
        # Business logic
        result = await service.upload_sale(sale_data)
        return UploadSaleResponse(success=True, ...)
        
    except ValidationError as e:
        logger.warning(f"Validation error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"error": e.message}
        )
        
    except NotFoundError as e:
        logger.warning(f"Not found: {e.message}")
        raise HTTPException(
            status_code=404,
            detail={"error": e.message}
        )
        
    except DatabaseError as e:
        logger.error(f"Database error: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Database operation failed"}
        )
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error"}
        )
```

---

## 📊 Logging & Monitoring

### 1. **Structured Logging**

```python
# ❌ MAUVAIS: Logs peu informatifs
logger.info("Sale uploaded")

# ✅ BON: Logs structurés avec contexte
logger.info(
    "Sale uploaded successfully",
    extra={
        "transaction_id": "TXN-001",
        "store_id": 5,
        "items_count": 3,
        "total_amount": 1200.50,
        "duration_ms": 234
    }
)

# Log output:
# 2024-04-29 14:23:45 - sales_service - INFO - Sale uploaded successfully
# transaction_id=TXN-001 store_id=5 items_count=3 total_amount=1200.50 duration_ms=234
```

### 2. **Health Checks**

```python
@app.get("/health")
async def health_check():
    """Health endpoint for monitoring"""
    try:
        # Test database
        db_ok = await db_manager.test_connection()
        
        # Test Key Vault (if prod)
        kv_ok = True
        if settings.ENVIRONMENT == "production":
            kv_ok = await kv_manager.test_access()
        
        status = "healthy" if (db_ok and kv_ok) else "degraded"
        
        return {
            "status": status,
            "database": "connected" if db_ok else "disconnected",
            "keyvault": "accessible" if kv_ok else "inaccessible",
            "version": VERSION
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy"}, 503
```

### 3. **Metrics Tracking**

```python
from prometheus_client import Counter, Histogram, Gauge

# Métriques
sales_uploaded_counter = Counter(
    'sales_uploaded_total',
    'Total sales uploaded'
)

upload_duration = Histogram(
    'sales_upload_duration_seconds',
    'Time to upload sale'
)

active_db_connections = Gauge(
    'db_active_connections',
    'Active database connections'
)

# Usage
with upload_duration.time():
    await service.upload_sale(data)
    sales_uploaded_counter.inc()
```

---

## 🎯 Résumé des Meilleures Pratiques

| Aspect | ❌ Mauvais | ✅ Bon |
|--------|-----------|--------|
| **Code** | Code copié-collé | DRY + SRP |
| **Types** | Pas de type hints | Type hints partout |
| **Noms** | `x`, `data`, `calc` | `calculate_net_amount` |
| **Secrets** | Hardcodés | Key Vault |
| **SQL** | String interpolation | Parameterized queries |
| **Validation** | Manuelle | Pydantic |
| **Performance** | Sync, N+1 queries | Async, aggregation |
| **Errors** | Generic errors | Custom exceptions |
| **Logging** | `print()` ou generic logs | Structured logging |
| **Testing** | Pas de tests | Unit + integration tests |

---

**Clean Code = Better Maintainability + Security + Performance**

Document mis à jour : 2024-04-29
