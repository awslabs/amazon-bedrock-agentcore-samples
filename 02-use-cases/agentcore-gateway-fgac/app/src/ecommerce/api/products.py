from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ecommerce.api.schemas import PriceUpdate, ProductCreate, ProductOut, StockUpdate
from ecommerce.auth.jwt import Principal, get_principal, require_admin
from ecommerce.db.session import get_session
from ecommerce.models import Product

router = APIRouter(prefix="/products", tags=["products"])

DbDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
AdminDep = Annotated[Principal, Depends(require_admin)]


@router.get("", response_model=list[ProductOut], operation_id="list_products")
def list_products(db: DbDep, _: PrincipalDep) -> list[Product]:
    """List all products available to authenticated customers."""
    return list(db.scalars(select(Product).order_by(Product.id)).all())


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_product",
)
def add_product(payload: ProductCreate, db: DbDep, _: AdminDep) -> Product:
    """Admin: create a new product."""
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU already exists") from e
    db.refresh(product)
    return product


@router.patch(
    "/{product_id}/price",
    response_model=ProductOut,
    operation_id="update_price",
)
def update_price(product_id: int, payload: PriceUpdate, db: DbDep, _: AdminDep) -> Product:
    """Admin: update a product's price."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    product.price = payload.price
    db.commit()
    db.refresh(product)
    return product


@router.patch(
    "/{product_id}/stock",
    response_model=ProductOut,
    operation_id="update_stock",
)
def update_stock(product_id: int, payload: StockUpdate, db: DbDep, _: AdminDep) -> Product:
    """Admin: update a product's stock level."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    product.stock = payload.stock
    db.commit()
    db.refresh(product)
    return product
