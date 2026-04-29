"""
Azure Key Vault integration module.
Handles secure credential retrieval in production environments.
"""

import os
import logging
from typing import Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class AzureKeyVaultManager:
    """
    Manages retrieval of secrets from Azure Key Vault.
    Uses Managed Identity in production (no credentials hardcoded).
    """
    
    def __init__(self, vault_url: str, tenant_id: Optional[str] = None):
        """
        Initialize Key Vault client.
        
        Args:
            vault_url: Azure Key Vault URL (https://vault-name.vault.azure.net/)
            tenant_id: Azure Tenant ID (optional, for service principal auth)
        """
        self.vault_url = vault_url
        self.tenant_id = tenant_id
        self._client: Optional[SecretClient] = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Initialize Key Vault client with appropriate credentials.
        
        Priority:
        1. Managed Identity (App Service production)
        2. Service Principal (if AZURE_CLIENT_ID and AZURE_CLIENT_SECRET set)
        3. Azure CLI credentials (local development with 'az login')
        """
        try:
            # Try DefaultAzureCredential (covers Managed Identity, CLI, etc.)
            credential = DefaultAzureCredential()
            logger.info(f"Initialized Key Vault client with DefaultAzureCredential")
            
        except Exception as e:
            # Fallback: Try Service Principal
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            
            if client_id and client_secret and self.tenant_id:
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=client_id,
                    client_secret=client_secret
                )
                logger.info("Initialized Key Vault client with Service Principal")
            else:
                logger.error(f"Failed to initialize Key Vault credentials: {e}")
                raise
        
        self._client = SecretClient(vault_url=self.vault_url, credential=credential)
    
    def get_secret(self, secret_name: str) -> str:
        """
        Retrieve a secret from Key Vault.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value
            
        Raises:
            Exception: If secret not found or authentication fails
        """
        if not self._client:
            raise RuntimeError("Key Vault client not initialized")
        
        try:
            secret = self._client.get_secret(secret_name)
            logger.debug(f"Retrieved secret '{secret_name}' from Key Vault")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to retrieve secret '{secret_name}': {e}")
            raise
    
    def set_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Store a secret in Key Vault (admin operation).
        
        Args:
            secret_name: Name of the secret
            secret_value: Value of the secret
        """
        if not self._client:
            raise RuntimeError("Key Vault client not initialized")
        
        try:
            self._client.set_secret(secret_name, secret_value)
            logger.info(f"Secret '{secret_name}' stored in Key Vault")
        except Exception as e:
            logger.error(f"Failed to store secret '{secret_name}': {e}")
            raise
    
    @staticmethod
    def get_credentials_from_keyvault(
        vault_url: str,
        db_host_secret: str = "db-host",
        db_user_secret: str = "db-user",
        db_password_secret: str = "db-password"
    ) -> dict:
        """
        Retrieve database credentials from Key Vault.
        
        Args:
            vault_url: Key Vault URL
            db_host_secret: Secret name for database host
            db_user_secret: Secret name for database user
            db_password_secret: Secret name for database password
            
        Returns:
            Dictionary with db_host, db_user, db_password
        """
        kv_manager = AzureKeyVaultManager(vault_url)
        
        return {
            "db_host": kv_manager.get_secret(db_host_secret),
            "db_user": kv_manager.get_secret(db_user_secret),
            "db_password": kv_manager.get_secret(db_password_secret),
        }


def setup_keyvault_credentials(settings) -> None:
    """
    Setup Key Vault credentials if in production.
    Updates settings with secrets retrieved from Key Vault.
    
    Args:
        settings: Settings object to update
    """
    if settings.ENVIRONMENT == "production" and settings.AZURE_KEYVAULT_URL:
        logger.info("Loading credentials from Azure Key Vault...")
        
        try:
            credentials = AzureKeyVaultManager.get_credentials_from_keyvault(
                vault_url=settings.AZURE_KEYVAULT_URL
            )
            
            settings.DB_HOST = credentials["db_host"]
            settings.DB_USER = credentials["db_user"]
            settings.DB_PASSWORD = credentials["db_password"]
            
            logger.info("Successfully loaded database credentials from Key Vault")
        except Exception as e:
            logger.error(f"Failed to load credentials from Key Vault: {e}")
            raise
