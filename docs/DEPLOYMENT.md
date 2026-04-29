# Guide de Déploiement - SmartRetail-Sync

## 🚀 Déploiement sur Azure

Ce guide détaille les étapes pour déployer SmartRetail-Sync en production sur Azure.

---

## 📋 Prérequis

- Compte Azure actif avec une souscription
- Azure CLI installé (`az --version`)
- Git installé
- Docker installé (optionnel, pour building local)
- Authentification Azure CLI : `az login`

---

## 🔧 Étape 1 : Créer l'Infrastructure Azure

### Option A : Script Automatisé (Recommandé)

#### Windows (PowerShell)
```powershell
# Ouvrir PowerShell comme administrateur
cd SmartRetail-Sync
.\infrastructure\setup.ps1
```

#### macOS/Linux (Bash)
```bash
chmod +x infrastructure/setup.sh
cd SmartRetail-Sync
./infrastructure/setup.sh
```

### Option B : Manual avec Azure CLI

```bash
# Variables
$RG="rg-smartretail-sync"
$LOCATION="westeurope"
$KV_NAME="kv-smartretail-$(date +%s)"

# 1. Resource Group
az group create \
  --name $RG \
  --location $LOCATION

# 2. Key Vault
az keyvault create \
  --resource-group $RG \
  --name $KV_NAME \
  --location $LOCATION

# 3. PostgreSQL
az postgres flexible-server create \
  --resource-group $RG \
  --name psql-smartretail-sync \
  --location $LOCATION \
  --admin-user dbadmin \
  --admin-password $(openssl rand -base64 32) \
  --sku-name "Standard_B1ms" \
  --tier "Burstable" \
  --storage-size 32 \
  --version 14

# ... (voir script setup.sh/setup.ps1 pour détails)
```

**Résultat:** ✅ Infrastructure déployée, secrets dans Key Vault

---

## 📊 Étape 2 : Initialiser la Base de Données

### 2.1 Récupérer les Paramètres de Connexion

```bash
# Récupérer le FQDN du serveur PostgreSQL
POSTGRES_HOST=$(az postgres flexible-server show \
  --resource-group rg-smartretail-sync \
  --name psql-smartretail-sync \
  --query fullyQualifiedDomainName -o tsv)

# Récupérer les secrets Key Vault
DB_USER=$(az keyvault secret show \
  --vault-name kv-smartretail-{random} \
  --name db-user \
  --query value -o tsv)

DB_PASSWORD=$(az keyvault secret show \
  --vault-name kv-smartretail-{random} \
  --name db-password \
  --query value -o tsv)
```

### 2.2 Appliquer le Schéma SQL

#### Option A : Via psql
```bash
# Si psql est installé localement
psql -h $POSTGRES_HOST \
     -U $DB_USER \
     -d smartretail_db \
     -f database/schema.sql

# À la demande de mot de passe, entrer: $DB_PASSWORD
```

#### Option B : Via Azure Portal
```
1. Aller à: https://portal.azure.com
2. Rechercher: PostgreSQL Servers → psql-smartretail-sync
3. Cliquer: "Query editor" (Preview)
4. Login avec dbadmin / password
5. Copier-coller le contenu de database/schema.sql
6. Exécuter
```

#### Option C : Via Cloud Shell
```bash
# Ouvrir Azure Cloud Shell dans le portal
az postgres flexible-server execute \
  --resource-group rg-smartretail-sync \
  --server-name psql-smartretail-sync \
  --database-name smartretail_db \
  --admin-user dbadmin \
  --file database/schema.sql
```

**Vérification:**
```bash
# Vérifier que les tables sont créées
psql -h $POSTGRES_HOST -U $DB_USER -d smartretail_db \
  -c "\dt"

# Résultat attendu:
# Schema |            Name            | Type  |  Owner
# --------+-----------------------------+-------+---------
#  public | dim_dates                  | table | dbadmin
#  public | dim_inventory              | table | dbadmin
#  public | dim_products               | table | dbadmin
#  public | dim_stores                 | table | dbadmin
#  public | fact_sales                 | table | dbadmin
```

**Résultat:** ✅ Schéma appliqué, données exemple insérées

---

## 🏗️ Étape 3 : Déployer le Code

### Option A : Git Integration (Recommandé pour CI/CD)

```bash
# 1. Pousser le code vers GitHub
git add .
git commit -m "SmartRetail-Sync initial commit"
git push origin main

# 2. Configurer le déploiement depuis App Service
az webapp deployment source config-zip \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --src-url https://github.com/your-username/SmartRetail-Sync/archive/refs/heads/main.zip

# OU via Azure Portal:
# App Service → Deployment → Deployment Center
# → GitHub → Autoriser → Sélectionner repo → Branche main
```

### Option B : Docker Container

```bash
# 1. Build l'image Docker
docker build -t smartretail-sync:latest -f Dockerfile .

# 2. Tagger pour ACR (Azure Container Registry)
REGISTRY_LOGIN_SERVER=$(az acr show \
  --resource-group rg-smartretail-sync \
  --name acr-smartretail \
  --query loginServer -o tsv)

docker tag smartretail-sync:latest \
  $REGISTRY_LOGIN_SERVER/smartretail-sync:latest

# 3. Login à ACR
az acr login --name acr-smartretail

# 4. Pousser l'image
docker push $REGISTRY_LOGIN_SERVER/smartretail-sync:latest

# 5. Configurer App Service pour utiliser l'image
az webapp config container set \
  --name app-smartretail-sync \
  --resource-group rg-smartretail-sync \
  --docker-custom-image-name $REGISTRY_LOGIN_SERVER/smartretail-sync:latest \
  --docker-registry-server-url https://$REGISTRY_LOGIN_SERVER \
  --docker-registry-server-user $(az acr credential show \
      --resource-group rg-smartretail-sync \
      --name acr-smartretail \
      --query username -o tsv) \
  --docker-registry-server-password $(az acr credential show \
      --resource-group rg-smartretail-sync \
      --name acr-smartretail \
      --query passwords[0].value -o tsv)

# 6. Redémarrer App Service
az webapp restart \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync
```

### Option C : ZIP Deployment

```bash
# 1. Créer un ZIP du backend
cd backend
zip -r ../smartretail-backend.zip .
cd ..

# 2. Déployer
az webapp deployment source config-zip \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --src smartretail-backend.zip
```

**Vérification:**
```bash
# Vérifier le statut du déploiement
az webapp deployment list-publishing-profiles \
  --name app-smartretail-sync \
  --resource-group rg-smartretail-sync

# Accéder à l'app
WEBAPP_URL=$(az webapp show \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --query defaultHostName -o tsv)

echo "App accessible à: https://$WEBAPP_URL"

# Test
curl https://$WEBAPP_URL/health
```

**Résultat:** ✅ Application déployée et accessible

---

## ⚙️ Étape 4 : Configurer l'Environnement Production

### 4.1 App Settings

```bash
az webapp config appsettings set \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --settings \
  ENVIRONMENT="production" \
  DEBUG="False" \
  LOG_LEVEL="INFO" \
  AZURE_KEYVAULT_URL="https://kv-smartretail-{random}.vault.azure.net/" \
  ENABLE_TELEMETRY="True"

# Vérifier
az webapp config appsettings list \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync
```

### 4.2 Logging & Monitoring

```bash
# Activer Application Insights
az webapp config set \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --app-insights-key $(az resource show \
      --resource-group rg-smartretail-sync \
      --name app-smartretail-sync \
      --resource-type "Microsoft.Insights/components" \
      --query properties.InstrumentationKey -o tsv)

# Configurer les logs
az webapp log config \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --web-server-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true

# Voir les logs
az webapp log tail \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync
```

### 4.3 CORS & Sécurité

```bash
# Configurer CORS pour Power BI
az webapp cors add \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --allowed-origins "https://app.powerbi.com" "https://powerbi.microsoft.com"

# Configurer HTTPS seulement
az webapp update \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --https-only true

# Configurer les certificats SSL
az appservice plan update \
  --resource-group rg-smartretail-sync \
  --name asp-smartretail-sync \
  --sku P1V2  # Si besoin de certificat personnalisé
```

---

## 🔐 Étape 5 : Configurer Power BI

### 5.1 Connection String

```
Server: psql-smartretail-{random}.postgres.database.azure.com
Database: smartretail_db
Username: dbadmin
Password: (from Key Vault)
Port: 5432
SSL Mode: require
```

### 5.2 Dans Power BI Desktop

```
1. Get Data → PostgreSQL Database
2. Server: psql-smartretail-{random}.postgres.database.azure.com
3. Database: smartretail_db
4. Mode: Direct Query (pour live data)
5. Credentials: dbadmin / password
6. Load tables:
   - vw_sales_summary
   - vw_inventory_alerts
   - dim_stores, dim_products, dim_dates
```

### 5.3 Créer les Dashboards

**Dashboard 1: Sales Performance**
- Revenus par région (carte)
- Tendance par mois (ligne)
- Top produits (bar)
- Transactions par magasin (table)

**Dashboard 2: Inventory Management**
- Stock critique (alerte rouge)
- Tendance stock (ligne)
- Produits à réapprovisionner (KPI)
- Historique mouvements (table)

---

## ✅ Vérification Post-Déploiement

### 1. Health Checks

```bash
APP_URL="https://app-smartretail-sync.azurewebsites.net"

# Test health endpoint
curl $APP_URL/health

# Résultat attendu:
# {
#   "status": "healthy",
#   "database": "connected",
#   "version": "1.0.0",
#   "environment": "production"
# }
```

### 2. Test API

```bash
# Uploader une vente test
curl -X POST $APP_URL/api/v1/sales/upload-sale \
  -H "Content-Type: application/json" \
  -d '{
    "store_code": "STR001",
    "transaction_id": "TXN-TEST-001",
    "items": [{
      "product_code": "PRD001",
      "quantity_sold": 1,
      "unit_price": 99.99,
      "discount_amount": 0,
      "tax_amount": 20.00
    }]
  }'

# Résultat attendu:
# {
#   "success": true,
#   "message": "Successfully inserted 1 sale items",
#   "sales_ids": [1],
#   "total_amount": 120.0,
#   "processed_items": 1
# }
```

### 3. Vérifier la BD

```bash
psql -h psql-smartretail-{random}.postgres.database.azure.com \
     -U dbadmin \
     -d smartretail_db \
     -c "SELECT COUNT(*) as total_sales FROM fact_sales;"

# Doit afficher les enregistrements insérés
```

### 4. Monitoring Azure

```bash
# Vérifier CPU/mémoire de l'App Service
az monitor metrics list \
  --resource /subscriptions/{sub-id}/resourceGroups/rg-smartretail-sync/providers/Microsoft.Web/sites/app-smartretail-sync \
  --interval PT5M

# Vérifier les erreurs
az monitor log-analytics query \
  --workspace {workspace-id} \
  --analytics-query "AppServiceLogsV2 | where ResourceType == 'Microsoft.Web/sites' | where ResourceName == 'app-smartretail-sync' | order by TimeGenerated desc"
```

---

## 🔄 Mise à Jour en Production

### Déployer une nouvelle version

```bash
# 1. Mettre à jour le code localement
git pull origin main
# ... faire les modifications ...

# 2. Commit et push
git add .
git commit -m "Fix: Update API"
git push origin main

# 3. Redéployer (automatique via GitHub Actions)
# OU manuel:
az webapp deployment source config-zip \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --src-url https://github.com/your-username/SmartRetail-Sync/archive/refs/heads/main.zip

# 4. Vérifier le déploiement
az webapp show \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync \
  --query state
```

---

## 🐛 Troubleshooting

### Erreur: "Cannot connect to database"

```bash
# Vérifier la chaîne de connexion
az keyvault secret show \
  --vault-name kv-smartretail-{random} \
  --name db-host

# Vérifier le firewall PostgreSQL
az postgres flexible-server firewall-rule list \
  --resource-group rg-smartretail-sync \
  --server-name psql-smartretail-{random}

# Ajouter l'IP si besoin
az postgres flexible-server firewall-rule create \
  --resource-group rg-smartretail-sync \
  --server-name psql-smartretail-{random} \
  --name AllowAllAzureIps \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 255.255.255.255
```

### Erreur: "Key Vault access denied"

```bash
# Vérifier la Managed Identity est assignée
az webapp identity show \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync

# Vérifier les permissions Key Vault
az keyvault role assignment list \
  --vault-name kv-smartretail-{random} \
  --role-assignment-name "Key Vault Secrets User"
```

### Erreur: "502 Bad Gateway"

```bash
# Vérifier les logs
az webapp log tail \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync

# Redémarrer l'app
az webapp restart \
  --resource-group rg-smartretail-sync \
  --name app-smartretail-sync

# Vérifier la santé
curl https://app-smartretail-sync.azurewebsites.net/health
```

---

## 📊 Coûts Estimés (Mensuel - France)

| Service | SKU | Coût |
|---------|-----|------|
| **App Service** | B1 (512 MB) | ~12€ |
| **PostgreSQL** | Flexible B1ms | ~30€ |
| **Key Vault** | Standard | ~0.50€ |
| **Storage** | 32 GB | ~1€ |
| **Data Transfer** | ~10GB/mois | ~1€ |
| **TOTAL** | | **~45€/mois** |

---

## 📞 Support & Escalation

- **Logs**: `az webapp log tail --name app-smartretail-sync`
- **Metrics**: Azure Portal → App Service → Metrics
- **Alerts**: Configurer via Azure Monitor
- **Support**: Microsoft Azure Support Portal

---

**Document mis à jour:** 2024-04-29
**Version:** 1.0.0
