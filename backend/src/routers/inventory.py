"""
Inventory API router.
Defines endpoints for inventory management operations.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from starlette.concurrency import run_in_threadpool

from src.config.settings import settings
from src.models.schemas import (
    InventoryRequest,
    InventoryResponse,
)
from src.services.database import DatabaseManager
from src.utils.errors import NotFoundError, DatabaseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["Inventory"])

_connection_pool: Optional[pg_pool.SimpleConnectionPool] = None


def get_inventory_connection_pool() -> pg_pool.SimpleConnectionPool:
    """Get a singleton synchronous PostgreSQL connection pool."""
    global _connection_pool

    if _connection_pool is None:
        if not all([settings.DB_HOST, settings.DB_USER, settings.DB_PASSWORD]):
            raise DatabaseError(
                "Database credentials not configured",
                details="Set DB_HOST, DB_USER, DB_PASSWORD in .env"
            )

        _connection_pool = DatabaseManager.create_sync_connection_pool(
            db_host=settings.DB_HOST,
            db_port=settings.DB_PORT,
            db_name=settings.DB_NAME,
            db_user=settings.DB_USER,
            db_password=settings.DB_PASSWORD,
        )

    return _connection_pool


def _fetch_low_stock_alerts(region: Optional[str], limit: int) -> List[dict]:
    """Fetch inventory rows that are at or near reorder level."""
    connection_pool = get_inventory_connection_pool()
    connection = None

    try:
        connection = connection_pool.getconn()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT
                    i.inventory_id,
                    p.product_code,
                    p.product_name,
                    s.store_code,
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
                WHERE p.is_active = TRUE
                  AND s.is_active = TRUE
                  AND i.stock_level <= (i.reorder_point * 1.5)
            """
            params = []

            if region:
                query += " AND s.region = %s"
                params.append(region)

            query += " ORDER BY i.stock_level ASC, p.product_code, s.store_code LIMIT %s"
            params.append(max(1, min(limit, 1000)))

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        if connection:
            connection_pool.putconn(connection)


def _update_inventory(inventory_request: InventoryRequest) -> dict:
    """Update or create one inventory row for a product-store pair."""
    connection_pool = get_inventory_connection_pool()
    connection = None

    try:
        connection = connection_pool.getconn()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT product_id FROM dim_products WHERE product_code = %s AND is_active = TRUE",
                (inventory_request.product_code,)
            )
            product = cursor.fetchone()
            if not product:
                raise NotFoundError(
                    f"Product with code '{inventory_request.product_code}' not found"
                )

            cursor.execute(
                "SELECT store_id FROM dim_stores WHERE store_code = %s AND is_active = TRUE",
                (inventory_request.store_code,)
            )
            store = cursor.fetchone()
            if not store:
                raise NotFoundError(
                    f"Store with code '{inventory_request.store_code}' not found"
                )

            cursor.execute("""
                INSERT INTO dim_inventory (
                    product_id, store_id, stock_level, reorder_point,
                    reorder_quantity, warehouse_location
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (product_id, store_id)
                DO UPDATE SET
                    stock_level = EXCLUDED.stock_level,
                    reorder_point = EXCLUDED.reorder_point,
                    reorder_quantity = EXCLUDED.reorder_quantity,
                    warehouse_location = EXCLUDED.warehouse_location,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING inventory_id
            """, (
                product["product_id"],
                store["store_id"],
                inventory_request.stock_level,
                inventory_request.reorder_point,
                inventory_request.reorder_quantity,
                inventory_request.warehouse_location,
            ))
            inventory_id = cursor.fetchone()["inventory_id"]
            connection.commit()

            return {
                "success": True,
                "message": "Inventory updated successfully",
                "inventory_id": inventory_id
            }
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection_pool.putconn(connection)


def _fetch_inventory_by_product(product_code: str) -> List[dict]:
    """Fetch inventory rows for a product across stores."""
    connection_pool = get_inventory_connection_pool()
    connection = None

    try:
        connection = connection_pool.getconn()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT
                    i.inventory_id,
                    p.product_code,
                    p.product_name,
                    s.store_code,
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
                WHERE p.product_code = %s
                  AND p.is_active = TRUE
                  AND s.is_active = TRUE
                ORDER BY s.store_code
            """, (product_code,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        if connection:
            connection_pool.putconn(connection)


@router.get(
    "/low-stock",
    response_model=List[InventoryResponse],
    summary="Get low stock alerts",
    description="Retrieve inventory items with stock levels below reorder point"
)
async def get_low_stock_alerts(
    region: str = None,
    limit: int = 50
) -> List[InventoryResponse]:
    """
    Retrieve inventory items with critical stock levels.
    
    Query parameters:
    - region: Filter by region (optional)
    - limit: Maximum number of records (default: 50)
    
    Returns list of InventoryResponse objects for items needing reorder.
    """
    try:
        logger.info(f"Retrieving low stock alerts: region={region}, limit={limit}")
        
        result = await run_in_threadpool(_fetch_low_stock_alerts, region, limit)
        return [InventoryResponse(**row) for row in result]
    
    except Exception as e:
        logger.error(f"Error retrieving low stock alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to retrieve low stock alerts"}
        )


@router.put(
    "/update",
    response_model=dict,
    summary="Update inventory",
    description="Update inventory stock levels for a product-store combination"
)
async def update_inventory(
    inventory_request: InventoryRequest
) -> dict:
    """
    Update inventory stock levels.
    
    Request body:
    - product_code: Product identifier
    - store_code: Store identifier
    - stock_level: New stock level
    - reorder_point: Point at which to reorder (optional)
    
    Returns:
    - success: Operation status
    - message: Operation result
    """
    try:
        logger.info(
            f"Updating inventory: "
            f"product={inventory_request.product_code}, "
            f"store={inventory_request.store_code}, "
            f"level={inventory_request.stock_level}"
        )
        
        return await run_in_threadpool(_update_inventory, inventory_request)
    
    except NotFoundError as e:
        logger.warning(f"Not found: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message}
        )
    
    except DatabaseError as e:
        logger.error(f"Database error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update inventory"}
        )


@router.get(
    "/by-product/{product_code}",
    response_model=List[InventoryResponse],
    summary="Get inventory by product",
    description="Retrieve inventory information for a specific product across all stores"
)
async def get_inventory_by_product(product_code: str) -> List[InventoryResponse]:
    """
    Get inventory status for a specific product.
    
    Path parameters:
    - product_code: Product identifier
    
    Returns list of InventoryResponse objects for all stores.
    """
    try:
        logger.info(f"Retrieving inventory for product: {product_code}")
        
        result = await run_in_threadpool(_fetch_inventory_by_product, product_code)
        if not result:
            raise NotFoundError(f"Product with code '{product_code}' not found")

        return [InventoryResponse(**row) for row in result]
    
    except Exception as e:
        logger.error(f"Error retrieving inventory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to retrieve inventory"}
        )
