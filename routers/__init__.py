from fastapi import APIRouter
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.users import router as users_router
from routers.secure import router as secure_router
from routers.chats import router as chats_router

router = APIRouter()

router.include_router(auth_router)

router.include_router(admin_router)

router.include_router(users_router)

router.include_router(secure_router)

router.include_router(chats_router)
