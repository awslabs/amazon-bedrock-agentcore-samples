from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str
    price: Decimal
    stock: int


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0, default=0)


class PriceUpdate(BaseModel):
    price: Decimal = Field(gt=0)


class StockUpdate(BaseModel):
    stock: int = Field(ge=0)


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, default=1)


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int


class CartOut(BaseModel):
    user_sub: str
    items: list[CartItemOut]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_sub: str
    total: Decimal
    items: list[OrderItemOut]
