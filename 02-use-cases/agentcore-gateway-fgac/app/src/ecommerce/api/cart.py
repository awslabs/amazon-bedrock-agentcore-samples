from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ecommerce.api.schemas import CartItemIn, CartItemOut, CartOut
from ecommerce.auth.jwt import Principal, get_principal
from ecommerce.db.session import get_session
from ecommerce.models import Cart, CartItem, Product

router = APIRouter(prefix="/cart", tags=["cart"])

DbDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


def _get_or_create_cart(db: Session, user_sub: str) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_sub == user_sub))
    if cart is None:
        cart = Cart(user_sub=user_sub)
        db.add(cart)
        db.flush()
    return cart


@router.post("/items", response_model=CartOut, operation_id="add_to_cart")
def add_to_cart(payload: CartItemIn, db: DbDep, principal: PrincipalDep) -> CartOut:
    """Customer: add a product to the user's cart, or increment quantity if already present."""
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    cart = _get_or_create_cart(db, principal.sub)
    existing = next((i for i in cart.items if i.product_id == payload.product_id), None)
    if existing is not None:
        existing.quantity += payload.quantity
    else:
        cart.items.append(CartItem(product_id=payload.product_id, quantity=payload.quantity))
    db.commit()
    db.refresh(cart)

    return CartOut(
        user_sub=cart.user_sub,
        items=[CartItemOut.model_validate(i) for i in cart.items],
    )
