from api import data_for_monitoring, notifications, statistics, user, wb_keys 
from app.logger import logger
from app.settings import settings
import contextlib
from fastapi import FastAPI, APIRouter, Response, Request
import logging
import orm
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from typing import AsyncIterator
import uvicorn



@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    orm.db_manager.init(settings.database_url)
    yield
    await orm.db_manager.close()

app = FastAPI(title=settings.app_name, lifespan=lifespan, debug=True)


app.include_router(user.router, prefix="/api/users", tags=["users"])
app.include_router(wb_keys.router, prefix="/api/wb_keys", tags=["wb_keys"])
app.include_router(statistics.router, prefix="/api", tags=["statistics"])
app.include_router(data_for_monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

if __name__ == "__main__":
    try:
        uvicorn.run(
            app,
            host=settings.app_host,
            port=settings.app_port,
        )
    except Exception as e:
        logger.error(e)
