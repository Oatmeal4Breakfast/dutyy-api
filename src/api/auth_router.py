from __future__ import annotations
from typing import Annotated

from fastapi import Depends, APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.deps import get_auth_service
from src.service.auth_service import AuthService
from src.logger import get_logger

logger = get_logger(__name__)


class SetPasswordRequest(BaseModel):
    raw_token: str
    new_password: str


router = APIRouter(prefix="/dutyy/api/v1", tags=["auth"])

_AuthService = Annotated[AuthService, Depends(get_auth_service)]


@router.post(path="/auth/set-password")
async def set_user_password(request: SetPasswordRequest, service: _AuthService):
    await service.set_password(
        raw_token=request.raw_token, new_password=request.new_password
    )
    return Response(status_code=204)
