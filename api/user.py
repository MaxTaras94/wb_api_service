from app.logger import logger
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import orm



class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str]
    source: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class APIUserResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: UserResponse


class APIUserListResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: list[UserResponse]


router = APIRouter()


@router.get("/get_user/{user_id}/", response_model=APIUserResponse)
async def get_user(
    user_id: int, session: AsyncSession = Depends(orm.get_session)
) -> JSONResponse:
    statement = select(orm.User).where(orm.User.telegram_id == user_id)
    user = await session.scalar(statement)
    logger.info(user)
    if not user:
        return JSONResponse(
            content={"status": "error", "message": "User not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    response_model = UserResponse.model_validate(user)
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_model.model_dump(),
        }
    )


@router.get("/get_users", response_model=APIUserListResponse)
async def get_users(session: AsyncSession = Depends(orm.get_session)) -> JSONResponse:
    users_results = await session.scalars(select(orm.User))
    response_data = [
        UserResponse.model_validate(u).model_dump() for u in users_results.all()
    ]
    logger.info(response_data)
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_data,
        }
    )


@router.post("/create_user", response_model=APIUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserResponse, session: AsyncSession = Depends(orm.get_session)
) -> JSONResponse:
    user_data_dump = user_data.model_dump()
    try:
        user_candidate = orm.User(**user_data_dump)
        session.add(user_candidate)
        await session.commit()
        await session.refresh(user_candidate)
        response_model = UserResponse.model_validate(user_candidate)
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "data": {"text_error": e},
                    },
            status_code=status.HTTP_400_BAD_REQUEST,
            )        
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_model.model_dump(),
        },
        status_code=status.HTTP_201_CREATED,
    )
    