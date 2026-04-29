"""
Sales service for handling sale operations and database interactions.
"""

import logging
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

from src.models.schemas import UploadSaleRequest, SaleItemRequest
from src.utils.errors import DatabaseError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class SalesService:
    """
    Service for managing sales operations.
    Handles data insertion, validation, and business logic.
    """
    
    def __init__(self, connection_pool):
        """
        Initialize sales service.
        
        Args:
            connection_pool: Database connection pool
        """
        self.connection_pool = connection_pool
    
    def upload_sale(self, sale_data: UploadSaleRequest) -> Dict:
        """
        Process and insert sale data into database.
        
        This method:
        1. Validates store and product existence
        2. Retrieves or creates inventory records
        3. Inserts sale records with proper relationships
        4. Updates inventory stock levels
        
        Args:
            sale_data: UploadSaleRequest object
            
        Returns:
            Dictionary with insertion results and summary
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If validation fails
            NotFoundError: If store or product not found
        """
        connection = None
        try:
            connection = self.connection_pool.getconn()
            cursor = connection.cursor()
            
            # 1. Validate store exists
            store_id = self._get_store_id(cursor, sale_data.store_code)
            if not store_id:
                raise NotFoundError(
                    f"Store with code '{sale_data.store_code}' not found"
                )
            
            # 2. Validate transaction_id is unique
            if self._transaction_exists(cursor, sale_data.transaction_id):
                raise ValidationError(
                    f"Transaction ID '{sale_data.transaction_id}' already exists"
                )
            
            # 3. Get or create date record
            date_id = self._get_or_create_date(
                cursor, 
                sale_data.sales_timestamp
            )
            
            # 4. Process each item
            sales_ids = []
            total_amount = Decimal('0')
            
            for item in sale_data.items:
                # Get product
                product_id = self._get_product_id(cursor, item.product_code)
                if not product_id:
                    raise NotFoundError(
                        f"Product with code '{item.product_code}' not found"
                    )
                
                # Get or create inventory
                inventory_id = self._get_or_create_inventory(
                    cursor, 
                    product_id, 
                    store_id
                )
                
                # Calculate amounts
                item_total = item.quantity_sold * item.unit_price
                net_amount = item_total - item.discount_amount + item.tax_amount
                total_amount += net_amount
                
                # Validate calculation
                if net_amount <= 0:
                    raise ValidationError(
                        f"Net amount must be positive for product '{item.product_code}'"
                    )
                
                # Insert sale record
                sale_id = self._insert_sale(
                    cursor,
                    date_id=date_id,
                    product_id=product_id,
                    store_id=store_id,
                    inventory_id=inventory_id,
                    quantity_sold=item.quantity_sold,
                    unit_price=item.unit_price,
                    total_amount=item_total,
                    discount_amount=item.discount_amount,
                    net_amount=net_amount,
                    tax_amount=item.tax_amount,
                    transaction_id=sale_data.transaction_id,
                    cashier_id=sale_data.cashier_id,
                    payment_method=sale_data.payment_method,
                    sales_timestamp=sale_data.sales_timestamp
                )
                
                sales_ids.append(sale_id)
                
                # Update inventory stock
                self._update_inventory_stock(
                    cursor,
                    inventory_id,
                    -item.quantity_sold  # Decrease stock
                )
            
            # Commit transaction
            connection.commit()
            
            logger.info(
                f"Sale uploaded successfully: "
                f"transaction_id={sale_data.transaction_id}, "
                f"items_count={len(sales_ids)}, "
                f"total_amount={total_amount}"
            )
            
            return {
                "success": True,
                "message": f"Successfully inserted {len(sales_ids)} sale items",
                "sales_ids": sales_ids,
                "total_amount": total_amount,
                "processed_items": len(sales_ids)
            }
        
        except (DatabaseError, ValidationError, NotFoundError) as e:
            if connection:
                connection.rollback()
            logger.error(f"Known error in upload_sale: {e.message}")
            raise
        
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Unexpected error in upload_sale: {e}")
            raise DatabaseError(
                "Failed to process sale data",
                details=str(e)
            )
        
        finally:
            if connection:
                self.connection_pool.putconn(connection)
    
    @staticmethod
    def _get_store_id(cursor, store_code: str) -> Optional[int]:
        """Get store ID by code."""
        cursor.execute(
            "SELECT store_id FROM dim_stores WHERE store_code = %s AND is_active = TRUE",
            (store_code,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    @staticmethod
    def _transaction_exists(cursor, transaction_id: str) -> bool:
        """Check if transaction already exists."""
        cursor.execute(
            "SELECT 1 FROM fact_sales WHERE transaction_id = %s LIMIT 1",
            (transaction_id,)
        )
        return cursor.fetchone() is not None
    
    @staticmethod
    def _get_product_id(cursor, product_code: str) -> Optional[int]:
        """Get product ID by code."""
        cursor.execute(
            "SELECT product_id FROM dim_products WHERE product_code = %s AND is_active = TRUE",
            (product_code,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    @staticmethod
    def _get_or_create_date(cursor, date: datetime) -> int:
        """Get or create date dimension record."""
        date_obj = date.date()
        
        cursor.execute(
            "SELECT date_id FROM dim_dates WHERE full_date = %s",
            (date_obj,)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        
        # Create if not exists
        cursor.execute("""
            INSERT INTO dim_dates 
            (full_date, day_of_week, day_name, month, month_name, quarter, year, is_weekend)
            VALUES (%s, EXTRACT(DOW FROM %s), TO_CHAR(%s, 'Day'), 
                    EXTRACT(MONTH FROM %s), TO_CHAR(%s, 'Month'), 
                    EXTRACT(QUARTER FROM %s), EXTRACT(YEAR FROM %s),
                    EXTRACT(DOW FROM %s) IN (0, 6))
            RETURNING date_id
        """, (date_obj, date_obj, date_obj, date_obj, date_obj, date_obj, date_obj, date_obj))
        
        return cursor.fetchone()[0]
    
    @staticmethod
    def _get_or_create_inventory(cursor, product_id: int, store_id: int) -> int:
        """Get or create inventory record."""
        cursor.execute(
            "SELECT inventory_id FROM dim_inventory WHERE product_id = %s AND store_id = %s",
            (product_id, store_id)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        
        # Create inventory record
        cursor.execute("""
            INSERT INTO dim_inventory (product_id, store_id, stock_level, reorder_point, reorder_quantity)
            VALUES (%s, %s, 0, 100, 200)
            RETURNING inventory_id
        """, (product_id, store_id))
        
        return cursor.fetchone()[0]
    
    @staticmethod
    def _insert_sale(
        cursor,
        date_id: int,
        product_id: int,
        store_id: int,
        inventory_id: int,
        quantity_sold: int,
        unit_price: Decimal,
        total_amount: Decimal,
        discount_amount: Decimal,
        net_amount: Decimal,
        tax_amount: Decimal,
        transaction_id: str,
        cashier_id: Optional[str],
        payment_method: str,
        sales_timestamp: datetime
    ) -> int:
        """Insert a sale record and return its ID."""
        cursor.execute("""
            INSERT INTO fact_sales 
            (date_id, product_id, store_id, inventory_id, quantity_sold, unit_price,
             total_amount, discount_amount, net_amount, tax_amount, transaction_id,
             cashier_id, payment_method, sales_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING sales_id
        """, (date_id, product_id, store_id, inventory_id, quantity_sold, unit_price,
              total_amount, discount_amount, net_amount, tax_amount, transaction_id,
              cashier_id, payment_method, sales_timestamp))
        
        return cursor.fetchone()[0]
    
    @staticmethod
    def _update_inventory_stock(
        cursor,
        inventory_id: int,
        quantity_change: int
    ) -> None:
        """Update inventory stock level."""
        cursor.execute("""
            UPDATE dim_inventory 
            SET stock_level = stock_level + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = %s
        """, (quantity_change, inventory_id))
