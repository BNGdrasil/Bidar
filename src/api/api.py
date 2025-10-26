# --------------------------------------------------------------------------
# API Router module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from fastapi import APIRouter

from .routes.auth import router as auth_router
from .routes.rbac import router as rbac_router
from .routes.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(rbac_router, tags=["rbac"])
