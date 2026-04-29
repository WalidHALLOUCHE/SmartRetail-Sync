# ============================================
# SmartRetail-Sync Azure Infrastructure Setup
# Creates the Azure resources required by the project.
# ============================================

$ErrorActionPreference = "Stop"

# Configuration
$ResourceGroup = "rg-smartretail-sync"
$Location = "westeurope"
$Suffix = Get-Random -Minimum 10000 -Maximum 99999
$KeyVaultName = "kv-smartretail$Suffix"
$PostgresServer = "psql-smartretail-$Suffix"
$PostgresAdmin = "dbadmin"
$PostgresPassword = [System.Convert]::ToBase64String(
    [System.Text.Encoding]::UTF8.GetBytes((New-Guid).ToString())
)
$DatabaseName = "smartretail_db"
$AppServicePlan = "asp-smartretail-sync"
$AppServiceName = "app-smartretail-sync-$Suffix"
$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "SmartRetail-Sync Infrastructure Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Login to Azure
if (-not $SubscriptionId) {
    Write-Host "Logging in to Azure..." -ForegroundColor Yellow
    az login
    $SubscriptionId = az account show --query id -o tsv
}

Write-Host "Using subscription: $SubscriptionId" -ForegroundColor Green

# 2. Create Resource Group
Write-Host ""
Write-Host "Creating resource group: $ResourceGroup..." -ForegroundColor Yellow
az group create `
    --name $ResourceGroup `
    --location $Location
Write-Host "Resource group ready" -ForegroundColor Green

# 3. Create Key Vault
Write-Host ""
Write-Host "Creating Azure Key Vault: $KeyVaultName..." -ForegroundColor Yellow
az keyvault create `
    --resource-group $ResourceGroup `
    --name $KeyVaultName `
    --location $Location `
    --enable-soft-delete true `
    --sku standard
Write-Host "Key Vault ready" -ForegroundColor Green

# 4. Create PostgreSQL Flexible Server
Write-Host ""
Write-Host "Creating PostgreSQL Flexible Server: $PostgresServer..." -ForegroundColor Yellow
az postgres flexible-server create `
    --resource-group $ResourceGroup `
    --name $PostgresServer `
    --location $Location `
    --admin-user $PostgresAdmin `
    --admin-password $PostgresPassword `
    --sku-name "Standard_B1ms" `
    --tier "Burstable" `
    --storage-size 32 `
    --version 14 `
    --high-availability "Disabled" `
    --backup-retention 7 `
    --public-access "All"
Write-Host "PostgreSQL server ready" -ForegroundColor Green

# 5. Create database
Write-Host ""
Write-Host "Creating database: $DatabaseName..." -ForegroundColor Yellow
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $PostgresServer `
    --database-name $DatabaseName
Write-Host "Database ready" -ForegroundColor Green

# 6. Store secrets in Key Vault
Write-Host ""
Write-Host "Storing secrets in Key Vault..." -ForegroundColor Yellow

$PostgresFqdn = "$PostgresServer.postgres.database.azure.com"

az keyvault secret set --vault-name $KeyVaultName --name "db-host" --value $PostgresFqdn
az keyvault secret set --vault-name $KeyVaultName --name "db-name" --value $DatabaseName
az keyvault secret set --vault-name $KeyVaultName --name "db-user" --value $PostgresAdmin
az keyvault secret set --vault-name $KeyVaultName --name "db-password" --value $PostgresPassword

Write-Host "Secrets stored in Key Vault" -ForegroundColor Green

# 7. Create App Service Plan
Write-Host ""
Write-Host "Creating App Service Plan: $AppServicePlan..." -ForegroundColor Yellow
az appservice plan create `
    --name $AppServicePlan `
    --resource-group $ResourceGroup `
    --sku B1 `
    --is-linux
Write-Host "App Service Plan ready" -ForegroundColor Green

# 8. Create App Service
Write-Host ""
Write-Host "Creating App Service: $AppServiceName..." -ForegroundColor Yellow
az webapp create `
    --resource-group $ResourceGroup `
    --plan $AppServicePlan `
    --name $AppServiceName `
    --runtime "PYTHON|3.11"
Write-Host "App Service ready" -ForegroundColor Green

# 9. Enable system-assigned Managed Identity
Write-Host ""
Write-Host "Enabling system-assigned Managed Identity..." -ForegroundColor Yellow
$PrincipalId = az webapp identity assign `
    --resource-group $ResourceGroup `
    --name $AppServiceName `
    --query principalId -o tsv
Write-Host "Managed Identity enabled" -ForegroundColor Green

# 10. Grant Key Vault access to Managed Identity
Write-Host ""
Write-Host "Granting Key Vault access to Managed Identity..." -ForegroundColor Yellow
az keyvault set-policy `
    --name $KeyVaultName `
    --object-id $PrincipalId `
    --secret-permissions get list
Write-Host "Key Vault access granted" -ForegroundColor Green

# 11. Configure App Settings
Write-Host ""
Write-Host "Configuring App Settings..." -ForegroundColor Yellow

$KeyVaultUrl = "https://$KeyVaultName.vault.azure.net/"

az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $AppServiceName `
    --settings `
    ENVIRONMENT="production" `
    DEBUG="False" `
    AZURE_KEYVAULT_URL=$KeyVaultUrl `
    DB_HOST=$PostgresFqdn `
    DB_NAME=$DatabaseName `
    DB_PORT="5432" `
    LOG_LEVEL="INFO"
Write-Host "App settings configured" -ForegroundColor Green

# 12. Summary
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Infrastructure setup complete" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "SUMMARY:" -ForegroundColor Yellow
Write-Host "  Resource Group:    $ResourceGroup"
Write-Host "  Key Vault:         $KeyVaultName"
Write-Host "  PostgreSQL Server: $PostgresServer"
Write-Host "  PostgreSQL FQDN:   $PostgresFqdn"
Write-Host "  App Service:       $AppServiceName"
Write-Host "  Managed Identity:  system-assigned"
Write-Host ""
Write-Host "Database credentials:"
Write-Host "  Admin User:     $PostgresAdmin"
Write-Host "  Admin Password: stored in $KeyVaultName/db-password"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Apply database schema: database/schema.sql"
Write-Host "  2. Deploy backend code to App Service"
Write-Host "  3. Configure Power BI connection to PostgreSQL"
Write-Host "=========================================" -ForegroundColor Cyan
