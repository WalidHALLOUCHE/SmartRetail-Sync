# SmartRetail-Sync - Guide de Démarrage Rapide ⚡

## 🎯 Objectif Final

Ce guide te permettra en **30 minutes** de :
1. ✅ Lancer l'API localement
2. ✅ Insérer des données test
3. ✅ Consulter Power BI
4. ✅ Comprendre l'architecture

---

## 🚀 Étape 1 : Préparation (5 min)

### 1.1 Installer les Prérequis

```bash
# Python 3.11+ (vérifier)
python --version

# Git (vérifier)
git --version

# PostgreSQL (vérifier)
psql --version
# Si pas installé: https://www.postgresql.org/download/

# Docker (optionnel, pour développement facile)
docker --version
```

### 1.2 Cloner le Projet

```bash
git clone https://github.com/your-username/SmartRetail-Sync.git
cd SmartRetail-Sync
```

---

## 🐳 Option A : Lancer avec Docker Compose (FACILE - 3 min)

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier que tout fonctionne
docker-compose ps

# Attendre ~10 secondes que PostgreSQL démarre
sleep 10

# Test de l'API
curl http://localhost:8000/health

# Test de la BD
psql -h localhost -U smartretail_user -d smartretail_db \
  -c "SELECT COUNT(*) FROM dim_stores;"
```

**Services disponibles:**
- 🌐 API Backend: http://localhost:8000
- 📚 Swagger Docs: http://localhost:8000/api/v1/docs
- 🗄️  PostgreSQL: localhost:5432
- 🎨 pgAdmin: http://localhost:5050

**➡️ Saute à Étape 3 (Test API)**

---

## 🖥️ Option B : Installation Manuelle (10 min)

### 2.1 Créer l'Environnement Python

```bash
# Créer l'environnement virtuel
python -m venv venv

# Activation
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Vérifier l'activation (prompt changera)
python --version
```

### 2.2 Installer les Dépendances

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 2.3 Configurer la Base de Données

#### A. Créer l'utilisateur PostgreSQL

```bash
# Ouvrir PostgreSQL
psql -U postgres

# Copier-coller ces commandes:
CREATE USER smartretail_user WITH PASSWORD 'smartretail_password';
CREATE DATABASE smartretail_db OWNER smartretail_user;
ALTER USER smartretail_user CREATEDB;
\q
```

#### B. Appliquer le Schéma

```bash
# Depuis le dossier SmartRetail-Sync
psql -U smartretail_user -d smartretail_db -f database/schema.sql

# Vérifier
psql -U smartretail_user -d smartretail_db -c "\dt"
```

### 2.4 Configurer le Backend

```bash
# Copier la configuration
cp backend/.env.example backend/.env

# Vérifier le fichier (les valeurs sont correctes par défaut)
cat backend/.env
```

### 2.5 Lancer le Backend

```bash
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Résultat attendu:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**➡️ Aller à Étape 3**

---

## ✅ Étape 3 : Tester l'API (5 min)

### 3.1 Health Check

```bash
curl http://localhost:8000/health

# Résultat attendu:
# {
#   "status": "healthy",
#   "timestamp": "2024-04-29T14:23:45.123456",
#   "service": "SmartRetail-Sync Sales API"
# }
```

### 3.2 Consulter la Documentation Interactive

Ouvrir dans le navigateur:
```
http://localhost:8000/api/v1/docs
```

Tu verras tous les endpoints avec la possibilité de les tester directement!

### 3.3 Uploader une Vente Test

#### Méthode 1: Via Swagger
1. Ouvrir http://localhost:8000/api/v1/docs
2. Trouver "POST /sales/upload-sale"
3. Cliquer "Try it out"
4. Copier-coller ce JSON:

```json
{
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
    },
    {
      "product_code": "PRD002",
      "quantity_sold": 1,
      "unit_price": 45.50,
      "discount_amount": 5.00,
      "tax_amount": 8.10
    }
  ]
}
```

5. Cliquer "Execute"

#### Méthode 2: Via curl

```bash
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
```

**Résultat attendu:**
```json
{
  "success": true,
  "message": "Successfully inserted 2 sale items",
  "sales_ids": [1, 2],
  "total_amount": 1199.97,
  "processed_items": 2
}
```

### 3.4 Vérifier la Données dans PostgreSQL

```bash
# Ouvrir PostgreSQL
psql -U smartretail_user -d smartretail_db

# Voir les ventes insérées
SELECT * FROM fact_sales LIMIT 5;

# Voir le résumé
SELECT * FROM vw_sales_summary LIMIT 5;

# Quitter
\q
```

---

## 📊 Étape 4 : Connecter Power BI (5 min)

### 4.1 Ouvrir Power BI Desktop

Télécharger si nécessaire: https://powerbi.microsoft.com/downloads/

### 4.2 Nouvelle Source de Données

1. **Get Data** → **PostgreSQL Database**
2. **Remplir les champs:**
   ```
   Server: localhost
   Database: smartretail_db
   ```
3. **Credentials:**
   ```
   Username: smartretail_user
   Password: smartretail_password
   ```
4. **Data Connectivity mode:** Direct Query (pour live data)

### 4.3 Charger les Données

Sélectionner:
- ✅ `vw_sales_summary`
- ✅ `vw_inventory_alerts`
- ✅ `dim_stores`
- ✅ `dim_products`
- ✅ `dim_dates`

Cliquer **Load**

### 4.4 Créer un Dashboard Simple

**Page 1: Sales Overview**
```
1. Carte: Stores avec Total Revenue
2. Graphique: Tendance Revenue par Date
3. Tableau: Sales Summary
```

**Sauvegarde:** File → Save as `SmartRetail-Sales.pbix`

---

## 📁 Structure du Projet (Comprendre le Code)

```
SmartRetail-Sync/
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── settings.py          ← Configuration (local vs Azure)
│   │   │   └── keyvault.py          ← Secrets Azure
│   │   ├── services/
│   │   │   ├── database.py          ← Connexions BD
│   │   │   └── sales_service.py     ← Logique métier
│   │   ├── routers/
│   │   │   ├── sales.py             ← Endpoints /sales
│   │   │   └── inventory.py         ← Endpoints /inventory
│   │   └── main.py                  ← Application FastAPI
│   ├── requirements.txt              ← Dépendances
│   └── .env.example                 ← Variables d'env
├── database/
│   └── schema.sql                   ← Star Schema PostgreSQL
├── infrastructure/
│   └── setup.ps1                    ← Deployment Azure
├── docs/
│   ├── ARCHITECTURE.md              ← Détails techniques
│   └── DEPLOYMENT.md                ← Guide Azure complet
└── README.md                        ← Ce projet
```

### Points Clés du Code

**1. Configuration Intelligente (settings.py)**
```python
# Local: Charge depuis .env
# Azure: Charge depuis Key Vault
if settings.ENVIRONMENT == "production":
    setup_keyvault_credentials(settings)
```

**2. Validation des Données (schemas.py)**
```python
# Pydantic valide chaque requête
class SaleItemRequest(BaseModel):
    product_code: str = Field(..., min_length=1)
    quantity_sold: int = Field(..., gt=0)
```

**3. Service Métier (sales_service.py)**
```python
# Logique d'insertion avec transactions
await sales_service.upload_sale(sale_data)
# - Valide store & products
# - Insère dans fact_sales
# - Met à jour inventory
# - Commit ou rollback
```

**4. Routers FastAPI (sales.py)**
```python
@router.post("/upload-sale")
async def upload_sale(sale_data: UploadSaleRequest):
    # Point d'entrée pour l'API
```

---

## 🎓 Concepts Clés Expliqués

### Star Schema

```
┌─────────────┐
│  dim_dates  │
└──────┬──────┘
       │
       ├─ fact_sales ◄────────┬────────────┐
       │                       │            │
       ├────────────────────────┤            │
                                │            │
                         ┌──────┴───────┐   │
                         │ dim_products │   │
                         └──────────────┘   │
                                            │
                                   ┌────────┴──────────┐
                                   │  dim_stores      │
                                   └──────────────────┘
```

**Pourquoi?** Optimisé pour les requêtes analytiques (Power BI)

### Azure Key Vault

```
┌─────────────────────┐
│ App Service         │
│                     │
│  ┌───────────────┐  │
│  │ DefaultAzure  │  │ (Managed Identity)
│  │ Credential    │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ Azure SDK     │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │ (Secure)
           ▼
    ┌─────────────────┐
    │  Key Vault      │
    │ ┌─────────────┐ │
    │ │ db-host     │ │
    │ │ db-user     │ │
    │ │ db-password │ │
    │ └─────────────┘ │
    └─────────────────┘
```

**Avantage:** Zero credentials dans le code!

### Async/Await

```python
# Sans async (bloquant):
result = get_data()  # Attend jusqu'à 1s
print(result)

# Avec async (non-bloquant):
result = await get_data()  # Autres requêtes peuvent procéder
print(result)  # 10x+ rapide avec 10 requêtes concurrentes
```

---

## 🔧 Commandes Utiles

### Développement

```bash
# Vérifier la BD
psql -U smartretail_user -d smartretail_db -c "SELECT COUNT(*) FROM fact_sales;"

# Voir les logs de l'API
tail -f backend/logs/smartretail_sync.log

# Réinitialiser la BD (attention!)
psql -U smartretail_user -d smartretail_db -f database/schema.sql

# Lancer les tests
pytest backend/tests/ -v

# Formater le code
black backend/src/

# Vérifier les types
mypy backend/src/
```

### Docker

```bash
# Arrêter les services
docker-compose down

# Supprimer les données (réinitialiser)
docker-compose down -v

# Voir les logs d'un service
docker-compose logs backend

# Accéder à PostgreSQL container
docker-compose exec postgres psql -U smartretail_user -d smartretail_db
```

### Azure (Production)

```bash
# Login
az login

# Voir les ressources
az resource list --resource-group rg-smartretail-sync

# Voir les logs
az webapp log tail --resource-group rg-smartretail-sync --name app-smartretail-sync

# Déployer
az webapp deployment source config-zip --src-url https://...
```

---

## ❓ Troubleshooting

### "Cannot connect to PostgreSQL"

```bash
# Vérifier que PostgreSQL fonctionne
psql -U postgres -c "SELECT version();"

# Vérifier l'utilisateur
psql -U smartretail_user -d smartretail_db -c "\du"

# Réinitialiser
dropdb smartretail_db
createdb smartretail_db -O smartretail_user
psql -U smartretail_user -d smartretail_db -f database/schema.sql
```

### "API ne répond pas"

```bash
# Vérifier que l'API fonctionne
curl http://localhost:8000/health

# Vérifier les logs
# Windows: consulter la fenêtre du terminal
# Linux: tail -f backend/logs/smartretail_sync.log

# Redémarrer l'API
# CTRL+C pour arrêter
# Puis relancer uvicorn
```

### "Erreur d'import Python"

```bash
# S'assurer que l'env virtuel est activé
which python  # Doit montrer le chemin du venv

# Réinstaller les dépendances
pip install -r backend/requirements.txt --force-reinstall
```

---

## 📚 Ressources Recommandées

**Pour comprendre le projet:**
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

**Pour Power BI:**
- [Power BI Getting Started](https://docs.microsoft.com/power-bi/fundamentals/)
- [PostgreSQL in Power BI](https://docs.microsoft.com/power-bi/connect-data/desktop-connect-postgresql)

**Pour Azure:**
- [App Service Docs](https://docs.microsoft.com/azure/app-service/)
- [Key Vault Best Practices](https://docs.microsoft.com/azure/key-vault/)
- [Managed Identity](https://docs.microsoft.com/azure/active-directory/managed-identities-azure-resources/)

---

## 🎯 Prochaines Étapes

### Après avoir testé localement:
1. ✅ Ajouter plus de données test
2. ✅ Créer des dashboards Power BI
3. ✅ Déployer sur Azure (voir `docs/DEPLOYMENT.md`)
4. ✅ Ajouter des tests unitaires
5. ✅ Configurer CI/CD avec GitHub Actions

### Pour la Production:
- Utiliser `infrastructure/setup.ps1` pour créer l'infra Azure
- Suivre `docs/DEPLOYMENT.md` pour le déploiement
- Configurer les alertes dans Azure Monitor

---

**🎉 Bravo! Tu as maintenant un système complet fonctionnel localement!**

Pour questions ou problèmes:
- 📖 Consulte `README.md` pour plus de détails
- 🏗️ Consulte `docs/ARCHITECTURE.md` pour le design
- 🚀 Consulte `docs/DEPLOYMENT.md` pour Azure

---

**Mis à jour:** 2024-04-29
**Version:** 1.0.0
