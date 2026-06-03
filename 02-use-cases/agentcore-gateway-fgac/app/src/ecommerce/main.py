from fastapi import FastAPI

from ecommerce import __version__
from ecommerce.api import cart, checkout, products

app = FastAPI(
    title="eCommerce API",
    version=__version__,
    description="PoC API for AgentCore Gateway demo",
    openapi_version="3.1.0",
)

app.include_router(products.router)
app.include_router(cart.router)
app.include_router(checkout.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
