"""
Sales API router.
Defines endpoints for sales data operations.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from starlette.concurrency import run_in_threadpool

from src.config.settings import settings
from src.models.schemas import (
    UploadSaleRequest,
    UploadSaleResponse,
    ErrorResponse,
    SalesSummaryResponse
)
from src.services.database import DatabaseManager
from src.services.sales_service import SalesService
from src.utils.errors import (
    SmartRetailException,
    NotFoundError,
    ValidationError as SmartRetailValidationError,
    DatabaseError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales", tags=["Sales"])

_connection_pool: Optional[pg_pool.SimpleConnectionPool] = None
_sales_service: Optional[SalesService] = None


def get_sales_service() -> SalesService:
    """Get a singleton SalesService backed by a sync connection pool."""
    global _connection_pool
    global _sales_service

    if _sales_service is None:
        if not all([settings.DB_HOST, settings.DB_USER, settings.DB_PASSWORD]):
            raise DatabaseError(
                "Database credentials not configured",
                details="Set DB_HOST, DB_USER, DB_PASSWORD in .env"
            )

        if _connection_pool is None:
            _connection_pool = DatabaseManager.create_sync_connection_pool(
                db_host=settings.DB_HOST,
                db_port=settings.DB_PORT,
                db_name=settings.DB_NAME,
                db_user=settings.DB_USER,
                db_password=settings.DB_PASSWORD,
            )

        _sales_service = SalesService(_connection_pool)

    return _sales_service


def _fetch_sales_summary(
    store_code: Optional[str],
    region: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int
) -> List[dict]:
    """Fetch aggregated sales data from PostgreSQL."""
    get_sales_service()
    connection = None

    try:
        connection = _connection_pool.getconn()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT
                    d.full_date::text AS full_date,
                    s.store_name,
                    s.region,
                    p.product_name,
                    p.category,
                    SUM(f.quantity_sold)::int AS total_quantity,
                    SUM(f.net_amount) AS total_revenue,
                    COUNT(DISTINCT f.transaction_id)::int AS transaction_count,
                    AVG(f.net_amount) AS avg_transaction_value
                FROM fact_sales f
                INNER JOIN dim_dates d ON f.date_id = d.date_id
                INNER JOIN dim_stores s ON f.store_id = s.store_id
                INNER JOIN dim_products p ON f.product_id = p.product_id
                WHERE 1 = 1
            """
            params = []

            if store_code:
                query += " AND s.store_code = %s"
                params.append(store_code)
            if region:
                query += " AND s.region = %s"
                params.append(region)
            if start_date:
                query += " AND d.full_date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND d.full_date <= %s"
                params.append(end_date)

            query += """
                GROUP BY d.full_date, s.store_name, s.region, p.product_name, p.category
                ORDER BY d.full_date DESC, s.store_name, p.product_name
                LIMIT %s
            """
            params.append(max(1, min(limit, 1000)))

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        if connection:
            _connection_pool.putconn(connection)


@router.post(
    "/upload-sale",
    response_model=UploadSaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload sales data",
    description="Process and insert real-time sales data into the database"
)
async def upload_sale(
    sale_data: UploadSaleRequest
) -> UploadSaleResponse:
    """
    Upload and process sales transaction data.
    
    This endpoint:
    1. Validates incoming sales data (store, products, amounts)
    2. Retrieves credentials from Azure Key Vault (production)
    3. Inserts records into the star schema fact and dimension tables
    4. Updates inventory stock levels
    5. Returns transaction summary
    
    Request body:
    - store_code: Store identifier (e.g., "STR001")
    - transaction_id: Unique transaction identifier
    - items: List of products sold with quantities and prices
    
    Returns:
    - success: Operation status
    - sales_ids: IDs of inserted sales records
    - total_amount: Total transaction amount
    - processed_items: Number of items processed
    
    Raises:
    - 400 Bad Request: Validation error in request data
    - 404 Not Found: Store or product not found
    - 500 Internal Server Error: Database or service error
    """
    try:
        logger.info(
            f"Received sales upload: "
            f"store={sale_data.store_code}, "
            f"transaction={sale_data.transaction_id}, "
            f"items={len(sale_data.items)}"
        )
        
        sales_service = get_sales_service()
        result = await run_in_threadpool(sales_service.upload_sale, sale_data)
        return UploadSaleResponse(**result)
    
    except SmartRetailValidationError as e:
        logger.warning(f"Validation error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    
    except NotFoundError as e:
        logger.warning(f"Not found error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": e.message
            }
        )
    
    except DatabaseError as e:
        logger.error(f"Database error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": "Database operation failed",
                "details": e.details if e.details else "Contact support"
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected error in upload_sale: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.get(
    "/summary",
    response_model=List[SalesSummaryResponse],
    summary="Get sales summary",
    description="Retrieve aggregated sales data grouped by date, store, and product"
)
async def get_sales_summary(
    store_code: str = None,
    region: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100
) -> List[SalesSummaryResponse]:
    """
    Get sales summary with optional filtering.
    
    Query parameters:
    - store_code: Filter by store (optional)
    - region: Filter by region (optional)
    - start_date: Start date in YYYY-MM-DD format (optional)
    - end_date: End date in YYYY-MM-DD format (optional)
    - limit: Maximum number of records to return (default: 100)
    
    Returns list of SalesSummaryResponse objects.
    """
    try:
        logger.info(
            f"Retrieving sales summary: "
            f"store={store_code}, region={region}, "
            f"start_date={start_date}, end_date={end_date}"
        )
        
        result = await run_in_threadpool(
            _fetch_sales_summary,
            store_code,
            region,
            start_date,
            end_date,
            limit
        )
        return [SalesSummaryResponse(**row) for row in result]
    
    except Exception as e:
        logger.error(f"Error retrieving sales summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "QUERY_ERROR",
                "message": "Failed to retrieve sales summary"
            }
        )


@router.get("/health", summary="Health check endpoint")
async def health_check() -> dict:
    """
    Basic health check endpoint for monitoring.
    
    Returns:
    - status: 'healthy' if service is running
    - timestamp: Current timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "SmartRetail-Sync Sales API"
    }
