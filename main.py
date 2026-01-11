from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from config.logger import setup_logging, logger
from config.settings import settings
from config.utils import init_db
from routers import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    #startup
    await init_db()
    # setup logger
    setup_logging()
    yield
    logger.info("FastAPI is disconnected")
    
app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# INCLUDE ROUTERS
app.include_router(
    router,
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.APP_RELOAD
    )