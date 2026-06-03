from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ecommerce.api.schemas import OrderOut
from ecommerce.auth.jwt import Principal, get_principal
from ecommerce.db.session import get_session
from ecommerce.models import Cart, Order, OrderItem

router = APIRouter(tags=["checkout"])

DbDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


@router.post(
    "/checkout",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="checkout",
)
def checkout(db: DbDep, principal: PrincipalDep) -> Order:
    """Customer: convert the current cart into an order, decrement stock, clear the cart."""
    cart = db.scalar(select(Cart).where(Cart.user_sub == principal.sub))
    if cart is None or not cart.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    total = Decimal("0")
    order = Order(user_sub=principal.sub, total=total)
    for item in cart.items:
        product = item.product
        if product.stock < item.quantity:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Insufficient stock for product {product.sku}",
            )
        product.stock -= item.quantity
        line_total = product.price * item.quantity
        total += line_total
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=item.quantity,
            )
        )

    order.total = total
    db.add(order)
    db.delete(cart)
    db.commit()
    db.refresh(order)
    return order
