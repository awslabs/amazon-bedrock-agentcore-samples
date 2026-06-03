"""Idempotent DB bootstrap: create tables and seed sample products.

Two ways to invoke:

* Local dev (against docker compose / podman Postgres):
      cd app && uv run python -m ecommerce.bootstrap

* Remote (against RDS, via ECS run-task with command override):
      python -m ecommerce.bootstrap

Reads connection settings from the same env vars the app uses
(``APP_DATABASE_URL`` or the ``DB_*`` parts). Safe to re-run.
"""

from decimal import Decimal

from sqlalchemy import select

from ecommerce.db.session import SessionLocal, engine
from ecommerce.models import Base, Product

SAMPLE_PRODUCTS: list[dict] = [
    {
        "sku": "PS5-STD",
        "name": "PlayStation 5 (Standard)",
        "description": "Sony PlayStation 5 console with disc drive.",
        "price": Decimal("499.00"),
        "stock": 25,
    },
    {
        "sku": "PS5-DE",
        "name": "PlayStation 5 Digital Edition",
        "description": "Sony PlayStation 5 digital-only console.",
        "price": Decimal("449.00"),
        "stock": 30,
    },
    {
        "sku": "STEAMDECK-512",
        "name": "Steam Deck OLED 512GB",
        "description": "Valve Steam Deck OLED handheld, 512GB.",
        "price": Decimal("549.00"),
        "stock": 15,
    },
    {
        "sku": "SWITCH2",
        "name": "Nintendo Switch 2",
        "description": "Nintendo Switch 2 console.",
        "price": Decimal("449.00"),
        "stock": 40,
    },
    {
        "sku": "XBOX-SX",
        "name": "Xbox Series X",
        "description": "Microsoft Xbox Series X console.",
        "price": Decimal("499.00"),
        "stock": 20,
    },
    {
        "sku": "ROG-ALLY-X",
        "name": "ASUS ROG Ally X",
        "description": "ASUS ROG Ally X handheld gaming PC.",
        "price": Decimal("799.00"),
        "stock": 10,
    },
]


def main() -> None:
    print("Creating tables (if not present)...")
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        existing_skus = set(db.scalars(select(Product.sku)).all())
        new_count = 0
        for spec in SAMPLE_PRODUCTS:
            if spec["sku"] in existing_skus:
                continue
            db.add(Product(**spec))
            new_count += 1
        db.commit()
        all_products = db.scalars(select(Product).order_by(Product.id)).all()

    print(f"Seeded {new_count} new product(s); {len(all_products)} total in DB.")
    for p in all_products:
        print(f"  [{p.id}] {p.sku:<14} {p.name:<35} ${p.price}  stock={p.stock}")


if __name__ == "__main__":
    main()
