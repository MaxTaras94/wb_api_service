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

@router.get("/get_status_check_subscription/")
async def get_status_check_subscription(session: AsyncSession = Depends(orm.get_session)
                                        ) -> JSONResponse:
    try:
        statement = select(orm.BotSettings.on_off)\
        .where(orm.BotSettings.setting_name == 'check_subscription')
        results = await session.execute(statement)
        status_check = results.scalar()
        # response_data = [BotSettingsResponse.model_validate(u).model_dump() for u in status_check]
    except Exception as e:
        logger.error(f"#Ошибка в функции get_status_check_subscription\nТекст ошибки: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
                }
        )
    return JSONResponse(
        content={
            "status": "ok",
            "is_checking": status_check
        }
    )
    
@router.post("/update_status_check_subscription/", status_code=status.HTTP_200_OK)
async def update_status_check_subscription(new_status: Dict,
                               session: AsyncSession = Depends(orm.get_session),
                                ) -> JSONResponse:
    try:
        statement = update(orm.BotSettings).where(orm.BotSettings.setting_name == 'check_subscription').values(on_off=new_status['is_checking'])
        notif_results = await session.execute(statement)
        await session.commit()
    except Exception as e:
        logger.error(f"#Ошибка в функции update_status_check_subscription\nТекст ошибки: {e}")
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
