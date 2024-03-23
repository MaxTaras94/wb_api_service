from app.logger import logger
import datetime
import orm
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, Depends, status, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid


router = APIRouter()

@router.get("/get_current_status/{user_telegram_id}")
async def get_current_status_subscription(user_telegram_id: int, 
                                          session: AsyncSession = Depends(orm.get_session)
                                          ) -> JSONResponse:
    try:
        statement = select(orm.CheckSubscribe.is_subscriber)\
        .where(orm.CheckSubscribe.user_telegram_id == user_telegram_id)
        results = await session.execute(statement)
        is_subscriber = results.scalar()
    except Exception as e:
        logger.error(f"#Ошибка work_with_subscribe в функции get_status_check_subscription\nТекст ошибки: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
                }
        )
    return JSONResponse(
        content={
            "status": "ok",
            "is_subscriber": is_subscriber
        }
    )
    
@router.post("/update_status_subscription/", status_code=status.HTTP_200_OK)
async def update_status_subscription(data: Dict,
                                     session: AsyncSession = Depends(orm.get_session),
                                     ) -> JSONResponse:
    try:
        statement = update(orm.CheckSubscribe).where(orm.CheckSubscribe.user_telegram_id == int(data['tg_user_id'])).values(is_subscriber=data['is_subscriber'])
        notif_results = await session.execute(statement)
        await session.commit()
    except Exception as e:
        logger.error(f"#Ошибка work_with_subscribe в функции update_status_check_subscription\nТекст ошибки: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
                }
        )
    return JSONResponse(
        content={
            "status": "ok"
            }
    )
