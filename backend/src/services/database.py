"""
Database connection and management service.
Handles PostgreSQL connection pooling and transaction management.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import psycopg2
from psycopg2 import pool, OperationalError
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import Settings, get_database_url

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL database connections and sessions.
    Implements connection pooling and error handling.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize database manager.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.db_url = get_database_url(settings)
        self._engine = None
        self._session_maker = None
        self._connection_pool: Optional[pool.SimpleConnectionPool] = None
    
    async def initialize(self) -> None:
        """
        Initialize async engine and session factory.
        Called at application startup.
        """
        try:
            # Convert PostgreSQL URL for async SQLAlchemy
            async_db_url = self.db_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            
            self._engine = create_async_engine(
                async_db_url,
                pool_size=self.settings.DB_POOL_SIZE,
                max_overflow=self.settings.DB_MAX_OVERFLOW,
                pool_timeout=self.settings.DB_POOL_TIMEOUT,
                pool_recycle=self.settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,  # Validate connections before use
                echo=self.settings.DEBUG,
            )
            
            self._session_maker = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            
            logger.info("Database engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise
    
    async def close(self) -> None:
        """
        Close database connections.
        Called at application shutdown.
        """
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions.
        Handles session creation, transaction management, and cleanup.
        
        Usage:
            async with db_manager.get_session() as session:
                result = await session.execute(query)
        
        Yields:
            AsyncSession instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        if not self._session_maker:
            raise RuntimeError("Database not initialized")
        
        session = self._session_maker()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in database transaction: {e}")
            raise
        finally:
            await session.close()
    
    async def test_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    @staticmethod
    def create_sync_connection_pool(
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        min_connections: int = 5,
        max_connections: int = 20
    ) -> pool.SimpleConnectionPool:
        """
        Create synchronous connection pool for batch operations.
        
        Args:
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            min_connections: Minimum pool size
            max_connections: Maximum pool size
            
        Returns:
            SimpleConnectionPool instance
        """
        try:
            connection_pool = pool.SimpleConnectionPool(
                min_connections,
                max_connections,
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password,
            )
            logger.info(f"Connection pool created: {min_connections}-{max_connections}")
            return connection_pool
        except OperationalError as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise


class DatabaseConnection:
    """
    Helper class for executing synchronous queries.
    Used for initialization scripts and maintenance operations.
    """
    
    def __init__(self, settings: Settings):
        """Initialize database connection."""
        self.settings = settings
    
    def connect(self) -> Optional[object]:
        """
        Create a single database connection.
        
        Returns:
            Connection object or None if failed
        """
        try:
            conn = psycopg2.connect(
                host=self.settings.DB_HOST,
                port=self.settings.DB_PORT,
                database=self.settings.DB_NAME,
                user=self.settings.DB_USER,
                password=self.settings.DB_PASSWORD,
            )
            logger.info("Database connection established")
            return conn
        except OperationalError as e:
            logger.error(f"Failed to connect to database: {e}")
            return None
    
    @staticmethod
    def execute_sql_file(connection: object, sql_file_path: str) -> bool:
        """
        Execute SQL commands from a file.
        
        Args:
            connection: psycopg2 connection object
            sql_file_path: Path to SQL file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_commands = f.read()
            
            with connection.cursor() as cursor:
                cursor.execute(sql_commands)
                connection.commit()
                logger.info(f"SQL file executed: {sql_file_path}")
                return True
        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to execute SQL file: {e}")
            return False
