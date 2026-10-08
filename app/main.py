from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.bookings import router as bookings_router
from app.config.settings import settings
from app.api.routes import admin

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
)


app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    chat_router,
    prefix="/api/v1",
)

app.include_router(
    bookings_router,
    prefix="/api/v1",
)

app.include_router(
    admin.router,           
    prefix="/api/v1",
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
    }