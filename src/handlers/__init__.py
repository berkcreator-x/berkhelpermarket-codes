from aiogram import Router

from src.handlers import admin, common, generations, improve_product, new_product, profile


def get_main_router() -> Router:
    """Aggregate all sub-routers into a single root router."""
    router = Router(name="root")
    router.include_router(common.router)
    router.include_router(admin.router)
    router.include_router(new_product.router)
    router.include_router(improve_product.router)
    router.include_router(profile.router)
    router.include_router(generations.router)
    return router


__all__ = ["get_main_router"]
