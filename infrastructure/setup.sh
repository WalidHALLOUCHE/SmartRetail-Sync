#!/bin/bash
# ============================================
# SmartRetail-Sync Azure Infrastructure Setup
# Creates the Azure resources required by the project.
# ============================================

set -euo pipefail

# Configuration
RESOURCE_GROUP="rg-smartretail-sync"
LOCATION="westeurope"
SUFFIX="$(date +%s)"
KEYVAULT_NAME="kv-smartretail${SUFFIX: -5}"
POSTGRES_SERVER="psql-smartretail-${SUFFIX: -5}"
POSTGRES_ADMIN="dbadmin"
POSTGRES_PASSWORD="$(openssl rand -base64 32)"
DATABASE_NAME="smartretail_db"
APP_SERVICE_PLAN="asp-smartretail-sync"
APP_SERVICE_NAME="app-smartretail-sync-${SUFFIX: -5}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"

echo "========================================="
echo "SmartRetail-Sync Infrastructure Setup"
echo "========================================="
echo ""

# 1. Login to Azure
if [ -z "$SUBSCRIPTION_ID" ]; then
    echo "Logging in to Azure..."
    az login
    SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
fi

echo "Using subscription: $SUBSCRIPTION_ID"

# 2. Create Resource Group
echo ""
echo "Creating resource group: $RESOURCE_GROUP..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION"
echo "Resource group ready"

# 3. Create Key Vault
echo ""
echo "Creating Azure Key Vault: $KEYVAULT_NAME..."
az keyvault create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$KEYVAULT_NAME" \
    --location "$LOCATION" \
    --enable-soft-delete true \
    --enable-purge-protection false \
    --sku standard
echo "Key Vault ready"

# 4. Create PostgreSQL Flexible Server
echo ""
echo "Creating PostgreSQL Flexible Server: $POSTGRES_SERVER..."
az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER" \
    --location "$LOCATION" \
    --admin-user "$POSTGRES_ADMIN" \
    --admin-password "$POSTGRES_PASSWORD" \
    --sku-name "Standard_B1ms" \
    --tier "Burstable" \
    --storage-size 32 \
    --version 14 \
    --high-availability "Disabled" \
    --backup-retention 7 \
    --geo-redundant-backup "Disabled" \
    --public-access "All"
echo "PostgreSQL server ready"

# 5. Create database
echo ""
echo "Creating database: $DATABASE_NAME..."
az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER" \
    --database-name "$DATABASE_NAME"
echo "Database ready"

# 6. Store secrets in Key Vault
echo ""
echo "Storing secrets in Key Vault..."

POSTGRES_FQDN="${POSTGRES_SERVER}.postgres.database.azure.com"

az keyvault secret set --vault-name "$KEYVAULT_NAME" --name "db-host" --value "$POSTGRES_FQDN"
az keyvault secret set --vault-name "$KEYVAULT_NAME" --name "db-name" --value "$DATABASE_NAME"
az keyvault secret set --vault-name "$KEYVAULT_NAME" --name "db-user" --value "$POSTGRES_ADMIN"
az keyvault secret set --vault-name "$KEYVAULT_NAME" --name "db-password" --value "$POSTGRES_PASSWORD"
echo "Secrets stored in Key Vault"

# 7. Create App Service Plan
echo ""
echo "Creating App Service Plan: $APP_SERVICE_PLAN..."
az appservice plan create \
    --name "$APP_SERVICE_PLAN" \
    --resource-group "$RESOURCE_GROUP" \
    --sku B1 \
    --is-linux
echo "App Service Plan ready"

# 8. Create App Service
echo ""
echo "Creating App Service: $APP_SERVICE_NAME..."
az webapp create \
    --resource-group "$RESOURCE_GROUP" \
    --plan "$APP_SERVICE_PLAN" \
    --name "$APP_SERVICE_NAME" \
    --runtime "PYTHON|3.11"
echo "App Service ready"

# 9. Enable system-assigned Managed Identity
echo ""
echo "Enabling system-assigned Managed Identity..."
PRINCIPAL_ID="$(az webapp identity assign \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_SERVICE_NAME" \
    --query principalId -o tsv)"
echo "Managed Identity enabled"

# 10. Grant Key Vault access to Managed Identity
echo ""
echo "Granting Key Vault access to Managed Identity..."
az keyvault set-policy \
    --name "$KEYVAULT_NAME" \
    --object-id "$PRINCIPAL_ID" \
    --secret-permissions get list
echo "Key Vault access granted"

# 11. Configure App Settings
echo ""
echo "Configuring App Settings..."
az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_SERVICE_NAME" \
    --settings \
    ENVIRONMENT="production" \
    DEBUG="False" \
    AZURE_KEYVAULT_URL="https://${KEYVAULT_NAME}.vault.azure.net/" \
    DB_HOST="$POSTGRES_FQDN" \
    DB_NAME="$DATABASE_NAME" \
    DB_PORT="5432" \
    LOG_LEVEL="INFO"
echo "App settings configured"

# 12. Summary
echo ""
echo "========================================="
echo "Infrastructure setup complete"
echo "========================================="
echo ""
echo "SUMMARY:"
echo "  Resource Group:    $RESOURCE_GROUP"
echo "  Key Vault:         $KEYVAULT_NAME"
echo "  PostgreSQL Server: $POSTGRES_SERVER"
echo "  PostgreSQL FQDN:   $POSTGRES_FQDN"
echo "  App Service:       $APP_SERVICE_NAME"
echo "  Managed Identity:  system-assigned"
echo ""
echo "Database credentials:"
echo "  Admin User:     $POSTGRES_ADMIN"
echo "  Admin Password: stored in $KEYVAULT_NAME/db-password"
echo ""
echo "Next steps:"
echo "  1. Apply database schema: database/schema.sql"
echo "  2. Deploy backend code to App Service"
echo "  3. Configure Power BI connection to PostgreSQL"
echo "========================================="
