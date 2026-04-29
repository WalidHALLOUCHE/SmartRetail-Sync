# SmartRetail-Sync 🚀

**Un projet d'automatisation complète du suivi des stocks et des ventes avec Azure & Power BI**

![Python](https://img.shields.io/badge/python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue) ![Azure](https://img.shields.io/badge/Azure-Cloud-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎯 Objectif

SmartRetail-Sync est un système complet de gestion des stocks et des ventes en temps réel, conçu pour :

- **Ingérer** les données de ventes en temps réel via une API FastAPI
- **Stocker** les données dans une structure en étoile (Star Schema) PostgreSQL
- **Sécuriser** les credentials avec Azure Key Vault
- **Héberger** l'API sur Azure App Service avec Managed Identity
- **Analyser** avec Power BI pour des insights décisionnels

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Power BI Dashboard                     │
│              (Reporting & Analytics)                     │
└─────────────────────┬───────────────────────────────────┘
                      │ Read (SQL)
┌─────────────────────▼───────────────────────────────────┐
│           PostgreSQL Flexible Server                    │
│       (Star Schema: 1 fact + 4 dimensions)             │
│   ├─ fact_sales (millions de transactions)             │
│   ├─ dim_dates, dim_products, dim_stores, dim_inventory│
│   └─ Views pour les alertes et résumés                │
└─────────────────────▲───────────────────────────────────┘
                      │ SQL Insert/Update
┌─────────────────────┴───────────────────────────────────┐
│       FastAPI Backend (Azure App Service)               │
│   ├─ POST /api/v1/sales/upload-sale                    │
│   ├─ GET  /api/v1/sales/summary                        │
│   ├─ GET  /api/v1/inventory/low-stock                  │
│   └─ Health checks & Monitoring                         │
└─────────────────────▲───────────────────────────────────┘
         │ Retrieve Secrets    │ Managed Identity
         ▼                     ▼
    ┌──────────────────────────────────────┐
    │    Azure Key Vault                   │
    │  - db-host                           │
    │  - db-user                           │
    │  - db-password                       │
    └──────────────────────────────────────┘
         ▲
         │ HTTPS (No hardcoded credentials)
┌────────┴──────────────────────────────────┐
│  POS Systems, Web APIs, Mobile Apps       │
│        (Clients sending sales data)       │
└───────────────────────────────────────────┘
```

---

## 📊 Star Schema (Modélisation)

### Concept

Le Star Schema offre :
- **Performance optimale** pour les requêtes analytiques
- **Clarté** avec un fait central et dimensions satellites
- **Intégrité référentielle** via contraintes et clés étrangères

### Schéma

```
                  ┌─────────────┐
                  │  dim_dates  │
                  │─────────────│
                  │ date_id (PK)│
                  │ full_date   │
                  │ day, month  │
                  │ quarter, yr │
                  └──────┬──────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    │                    ▼
┌──────────────┐         │            ┌──────────────────┐
│  dim_stores  │         │            │  dim_products    │
├──────────────┤         │            ├──────────────────┤
│ store_id(PK) │         │            │ product_id (PK)  │
│ store_code   │         │            │ product_code     │
│ store_name   │         │            │ product_name     │
│ city, region │         │            │ category         │
└──────────────┘         │            └──────────────────┘
    │                    │                    │
    │            ┌───────▼────────┐           │
    └───────────►│  fact_sales    │◄──────────┘
             ┌──┤                │
             │  │ date_id (FK)   │
             │  │ product_id(FK) │
             │  │ store_id (FK)  │
             │  │ inventory_id(FK)
             │  │                │
             │  │ quantity_sold  │
             │  │ unit_price     │
             │  │ total_amount   │
             │  │ net_amount     │
             │  └────────────────┘
             │
    ┌────────▼──────────────┐
    │  dim_inventory         │
    ├────────────────────────┤
    │ inventory_id (PK)      │
    │ product_id (FK)        │
    │ store_id (FK)          │
    │ stock_level            │
    │ reorder_point          │
    └────────────────────────┘
```

### Tables

| Table | Rows | Description |
|-------|------|-------------|
| **fact_sales** | Millions | Transactions de ventes (mesures: quantité, prix, montants) |
| **dim_dates** | 365-730 | Dimension temporelle (jours, mois, trimestres, années) |
| **dim_products** | Milliers | Dimension produits (code, nom, catégorie, fournisseur) |
| **dim_stores** | Centaines | Dimension magasins (code, nom, région, gestionnaire) |
| **dim_inventory** | Milliers | Dimension inventaire (stock actuel, points de réapprovisionnement) |

---

## 🛠️ Stack Technologique

### Backend
- **FastAPI** : Framework web moderne et rapide (async)
- **Python 3.11** : Langage de programmation
- **Pydantic** : Validation de données avec typage fort
- **SQLAlchemy** : ORM pour requêtes SQL asynchrones

### Base de Données
- **PostgreSQL 15** : Système de gestion relationnel robuste
- **Connexion Pool** : `psycopg2` pour une performance optimale
- **Views & Triggers** : Logique métier au niveau BD

### Sécurité & Cloud
- **Azure Key Vault** : Gestion des secrets (DB credentials)
- **Azure App Service** : Hébergement serverless de l'API
- **Managed Identity** : Authentification sans credentials hardcodées
- **DefaultAzureCredential** : Intégration transparente Azure SDK

### Monitoring & Déploiement
- **Docker** : Containerisation de l'application
- **Docker Compose** : Orchestration locale (dev)
- **Azure CLI** : Infrastructure as Code

---

## 🚀 Démarrage Rapide

### 1. Prérequis

```bash
# Installations
- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optionnel)
- Azure CLI (pour déploiement production)
- Git
```

### 2. Installation Locale

```bash
# Clone du projet
git clone https://github.com/yourusername/SmartRetail-Sync.git
cd SmartRetail-Sync

# Créer l'environnement virtuel
python -m venv venv

# Activation
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Installer les dépendances
pip install -r backend/requirements.txt

# Copier la configuration
cp backend/.env.example backend/.env

# Éditer .env avec vos paramètres PostgreSQL locaux
```

### 3. Configuration PostgreSQL (Local)

```bash
# Créer l'utilisateur et la base
psql -U postgres -c "CREATE USER smartretail_user WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE smartretail_db OWNER smartretail_user;"

# Appliquer le schéma
psql -U smartretail_user -d smartretail_db -f database/schema.sql

# Vérifier
psql -U smartretail_user -d smartretail_db -c "\dt"
```

### 4. Lancer l'Application

#### Localement (Direct)
```bash
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### Avec Docker Compose
```bash
docker-compose up --build

# Services disponibles:
# - Backend:  http://localhost:8000
# - Docs:     http://localhost:8000/api/v1/docs
# - pgAdmin:  http://localhost:5050
```

### 5. Test de l'API

```bash
# Health check
curl http://localhost:8000/health

# Uploader une vente
curl -X POST http://localhost:8000/api/v1/sales/upload-sale \
  -H "Content-Type: application/json" \
  -d '{
    "store_code": "STR001",
    "transaction_id": "TXN-2024-001",
    "cashier_id": "CASH001",
    "payment_method": "CARD",
    "items": [
      {
        "product_code": "PRD001",
        "quantity_sold": 2,
        "unit_price": 999.99,
        "discount_amount": 0,
        "tax_amount": 199.98
      }
    ]
  }'

# Accéder à la documentation interactive
# Ouvrir: http://localhost:8000/api/v1/docs
```

---

## 📋 Déploiement Azure

### 1. Créer l'Infrastructure

```bash
# Utiliser le script de setup (PowerShell)
.\infrastructure\setup.ps1

# OU avec le script bash
bash infrastructure/setup.sh

# Cela crée:
# - Resource Group
# - Azure Key Vault
# - PostgreSQL Flexible Server
# - App Service Plan & App Service
# - Managed Identity avec accès Key Vault
```

### 2. Appliquer le Schéma PostgreSQL

```bash
# Récupérer la connexion de la BD depuis les outputs du script
# Puis:
psql -h <postgres-server-fqdn> -U dbadmin -d smartretail_db -f database/schema.sql

# Ou via Azure Portal: Query Editor
```

### 3. Déployer le Code

```bash
# Créer une image Docker
docker build -t smartretail-sync:latest -f Dockerfile .

# Pousser vers Azure Container Registry (si utilisé)
az acr build --registry <acr-name> --image smartretail-sync:latest .

# OU via Git Deployment (App Service)
# Connecter votre repository GitHub
# Configurer CI/CD automatique
```

### 4. Configurer les Paramètres de l'App Service

```bash
# Les secrets sont automatiquement récupérés depuis Key Vault
# Vérifier les App Settings:
az webapp config appsettings list \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync
```

---

## 🔐 Gestion des Secrets (Architecture Hybride)

### Environnement Local (Development)

```python
# .env file
DB_HOST=localhost
DB_USER=smartretail_user
DB_PASSWORD=local_password
ENVIRONMENT=local
```

### Azure App Service (Production)

```python
# DefaultAzureCredential découvre automatiquement:
# 1. Managed Identity (priorité)
# 2. Environment variables
# 3. Azure CLI credentials

# Aucun mot de passe dans le code !
```

### Configuration Intelligente (`settings.py`)

```python
from src.config.keyvault import setup_keyvault_credentials
from src.config.settings import settings

# En production:
if settings.ENVIRONMENT == "production":
    setup_keyvault_credentials(settings)  # Charge depuis Key Vault
    
# En développement:
# Charge depuis .env automatiquement
```

---

## 📊 Intégration Power BI

### 1. Connexion à PostgreSQL

```
Power BI Desktop → Get Data → PostgreSQL Database

Server:   <postgres-fqdn>
Database: smartretail_db
Username: dbadmin
Password: (from Key Vault)
```

### 2. Requêtes Recommandées

```sql
-- Vue: Sales Summary (déjà créée)
SELECT * FROM vw_sales_summary
WHERE full_date >= DATE '2024-01-01'
ORDER BY full_date DESC;

-- Vue: Low Stock Alerts
SELECT * FROM vw_inventory_alerts
WHERE stock_status IN ('REORDER_NEEDED', 'LOW_STOCK')
ORDER BY stock_level ASC;

-- Analyse personnalisée
SELECT 
    d.year,
    d.month_name,
    s.region,
    p.category,
    SUM(f.quantity_sold) as total_qty,
    SUM(f.net_amount) as total_revenue
FROM fact_sales f
JOIN dim_dates d ON f.date_id = d.date_id
JOIN dim_stores s ON f.store_id = s.store_id
JOIN dim_products p ON f.product_id = p.product_id
GROUP BY d.year, d.month_name, s.region, p.category
ORDER BY d.year DESC, d.month DESC, total_revenue DESC;
```

### 3. Dashboards Suggérés

- **Sales Performance** : Revenus par région, magasin, produit
- **Inventory Management** : Stock critique, alertes de réapprovisionnement
- **Trend Analysis** : Évolution des ventes dans le temps
- **Product Analysis** : Produits top-vendus, catégories

---

## 🔍 Bonnes Pratiques Implémentées

### Clean Code
- ✅ **Modularité** : Services, modèles, routeurs séparés
- ✅ **Type Hints** : Typage fort avec Pydantic
- ✅ **Documentation** : Docstrings détaillées sur chaque fonction
- ✅ **Error Handling** : Exceptions custom avec messages clairs
- ✅ **Logging** : Logs structurés à tous les niveaux

### Sécurité
- ✅ **Secrets Management** : Azure Key Vault, pas de hardcoding
- ✅ **Managed Identity** : Pas de credentials d'utilisateurs
- ✅ **Validation** : Pydantic valide toutes les inputs
- ✅ **SQL Injection** : Utilise parametrized queries
- ✅ **CORS** : Contrôlé à la source

### Performance
- ✅ **Connection Pooling** : Réutilisation de connexions
- ✅ **Indexes** : Stratégiquement placés sur `fact_sales`
- ✅ **Async/Await** : FastAPI asynchrone par défaut
- ✅ **Star Schema** : Optimisé pour les requêtes analytiques

### Observabilité
- ✅ **Health Checks** : Endpoint `/health` pour monitoring
- ✅ **Logging Structuré** : Timestamps, niveaux, contexte
- ✅ **Metrics** : Compteurs pour les uploads et erreurs
- ✅ **Error Tracking** : Messages détaillés avec contexte

---

## 📁 Structure du Projet

```
SmartRetail-Sync/
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── settings.py          # Configuration app (local/Azure)
│   │   │   └── keyvault.py          # Intégration Azure Key Vault
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic models (validation)
│   │   ├── services/
│   │   │   ├── database.py          # Connection pool, sessions
│   │   │   └── sales_service.py     # Logique métier ventes
│   │   ├── routers/
│   │   │   ├── sales.py             # Endpoints /sales
│   │   │   └── inventory.py         # Endpoints /inventory
│   │   ├── utils/
│   │   │   ├── logger.py            # Configuration logging
│   │   │   └── errors.py            # Exceptions custom
│   │   └── main.py                  # Application FastAPI
│   ├── requirements.txt              # Dépendances Python
│   └── .env.example                 # Template configuration
├── database/
│   └── schema.sql                   # Star Schema PostgreSQL
├── infrastructure/
│   ├── setup.ps1                    # Script setup (PowerShell)
│   └── setup.sh                     # Script setup (Bash)
├── docs/
│   ├── ARCHITECTURE.md              # Détails architecture
│   └── DATA_MODEL.md                # Détails Star Schema
├── Dockerfile                        # Image Docker
├── docker-compose.yml               # Orchestration locale
└── README.md                        # Ce fichier
```

---

## 🧪 Tests

```bash
# Tests unitaires
pytest backend/tests/ -v

# Tests d'intégration (avec BD)
pytest backend/tests/integration/ -v

# Couverture de code
pytest --cov=backend/src backend/tests/

# Linting
flake8 backend/src/
black backend/src/ --check
mypy backend/src/
```

---

## 🤝 Contribution

Les contributions sont bienvenues! Please:

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push à la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

---

## 📝 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour les détails.

---

## 📞 Support

Pour les questions ou problèmes :
- 📧 Email : support@smartretail-sync.dev
- 🐛 Issues : [GitHub Issues](https://github.com/yourusername/SmartRetail-Sync/issues)
- 💬 Discussions : [GitHub Discussions](https://github.com/yourusername/SmartRetail-Sync/discussions)

---

## 🙏 Remerciements

- Azure Team pour les services cloud
- FastAPI & PostgreSQL communities
- Tous les contributeurs

---

**Made with ❤️ for data engineering & analytics**
