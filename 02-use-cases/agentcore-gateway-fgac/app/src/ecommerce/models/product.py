from decimal import Decimal

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ecommerce.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000), default="")
    price: Mapped[Decimal] = mapped_column()
    stock: Mapped[int] = mapped_column(default=0)
