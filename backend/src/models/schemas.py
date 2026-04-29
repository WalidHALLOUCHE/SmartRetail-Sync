"""
Pydantic models for data validation and serialization.
Defines request/response schemas for API endpoints.
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, validator


# ============================================
# SALE DATA MODELS
# ============================================

class SaleItemRequest(BaseModel):
    """Request model for individual sale item."""
    
    product_code: str = Field(..., min_length=1, max_length=50)
    quantity_sold: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., decimal_places=2, gt=0)
    discount_amount: Decimal = Field(default=Decimal('0'), decimal_places=2, ge=0)
    tax_amount: Decimal = Field(default=Decimal('0'), decimal_places=2, ge=0)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }
    
    @validator('unit_price', pre=True)
    def convert_unit_price_to_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v
    
    @validator('discount_amount', pre=True)
    def convert_discount_to_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v
    
    @validator('tax_amount', pre=True)
    def convert_tax_to_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v
    
    @validator('discount_amount')
    def validate_discount(cls, v, values):
        if 'unit_price' in values:
            max_discount = values['unit_price'] * Decimal('0.5')
            if v > max_discount:
                raise ValueError('Discount cannot exceed 50% of unit price')
        return v


class UploadSaleRequest(BaseModel):
    """Request model for uploading sales data."""
    
    store_code: str = Field(..., min_length=1, max_length=50)
    transaction_id: str = Field(..., min_length=1, max_length=100)
    cashier_id: Optional[str] = Field(default=None, max_length=50)
    payment_method: str = Field(default="CASH", max_length=50)
    sales_timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    items: List[SaleItemRequest] = Field(..., min_items=1)
    
    class Config:
        schema_extra = {
            "example": {
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
            }
        }


class UploadSaleResponse(BaseModel):
    """Response model for sale upload."""
    
    success: bool
    message: str
    sales_ids: List[int] = []
    total_amount: Decimal = Decimal('0')
    processed_items: int = 0
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


# ============================================
# INVENTORY MODELS
# ============================================

class InventoryRequest(BaseModel):
    """Request model for inventory update."""
    
    product_code: str = Field(..., min_length=1, max_length=50)
    store_code: str = Field(..., min_length=1, max_length=50)
    stock_level: int = Field(..., ge=0)
    reorder_point: int = Field(default=100, ge=0)
    reorder_quantity: int = Field(default=200, gt=0)
    warehouse_location: Optional[str] = Field(default=None, max_length=100)


class InventoryResponse(BaseModel):
    """Response model for inventory data."""
    
    inventory_id: int
    product_code: str
    product_name: str
    store_code: str
    stock_level: int
    reorder_point: int
    stock_status: str  # NORMAL, LOW_STOCK, REORDER_NEEDED


# ============================================
# PRODUCT MODELS
# ============================================

class ProductRequest(BaseModel):
    """Request model for product creation."""
    
    product_code: str = Field(..., min_length=1, max_length=50)
    product_name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: Optional[str] = Field(default=None, max_length=100)
    price_range: Optional[str] = Field(default=None, max_length=50)
    supplier_id: Optional[int] = None
    is_active: bool = True


class ProductResponse(BaseModel):
    """Response model for product data."""
    
    product_id: int
    product_code: str
    product_name: str
    category: str
    subcategory: Optional[str]
    is_active: bool
    created_at: datetime


# ============================================
# STORE MODELS
# ============================================

class StoreRequest(BaseModel):
    """Request model for store creation."""
    
    store_code: str = Field(..., min_length=1, max_length=50)
    store_name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    region: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    store_type: Optional[str] = Field(default=None, max_length=50)
    manager_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = True


class StoreResponse(BaseModel):
    """Response model for store data."""
    
    store_id: int
    store_code: str
    store_name: str
    city: str
    region: str
    country: str
    store_type: Optional[str]
    is_active: bool


# ============================================
# ANALYTICS MODELS
# ============================================

class SalesSummaryResponse(BaseModel):
    """Response model for sales summary."""
    
    full_date: str
    store_name: str
    region: str
    product_name: str
    category: str
    total_quantity: int
    total_revenue: Decimal
    transaction_count: int
    avg_transaction_value: Decimal
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


# ============================================
# ERROR MODELS
# ============================================

class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    success: bool = False
    error_code: str
    message: str
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationError(ErrorResponse):
    """Validation error response."""
    
    error_code: str = "VALIDATION_ERROR"
    fields: Optional[dict] = None


# ============================================
# HEALTH CHECK MODELS
# ============================================

class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    database_connection: bool
    keyvault_connection: Optional[bool] = None
