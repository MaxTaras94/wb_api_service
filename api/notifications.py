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



class NotificationsResponse(BaseModel):
    id: int
    user_telegram_id: int
    type_operation: str
    is_checking: bool
    
    model_config = ConfigDict(from_attributes=True)

class NotificationsResponse4Update(BaseModel):
    id: int
    is_checking: bool
    
    model_config = ConfigDict(from_attributes=True)


class NotificationsListResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: list[NotificationsResponse]


router = APIRouter()

    

@router.get("/get_all/", response_model=NotificationsListResponse)
async def get_all_notifications(user_telegram_id: int, 
                                key_id: int,
                                session: AsyncSession = Depends(orm.get_session)
                                ) -> JSONResponse:
    try:
        statement = select(orm.Notification, orm.WB.user_telegram_id)\
        .join(orm.WB, orm.Notification.wb_api_keys_id == orm.WB.id)\
        .where(orm.WB.user_telegram_id == user_telegram_id,
               orm.WB.id == key_id).\
            options(selectinload(orm.Notification.type_operation))
        notif_results = await session.execute(statement)
        notifications = notif_results.scalars().all()
        response_data = [
            NotificationsResponse(
                id=notification.id,
                user_telegram_id=user_telegram_id,
                type_operation = notification.type_operation.type_operation,
                is_checking=notification.is_checking,
            ).dict() for notification in notifications
        ]
    except Exception as e:
        logger.error(f"#Ошибка в функции get_all_notifications\nТекст ошибки: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
                }
        )
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_data
        }
    )
    
@router.post("/update/", response_model=NotificationsResponse4Update, status_code=status.HTTP_200_OK)
async def update_notifications(notific_data: Dict,
                               session: AsyncSession = Depends(orm.get_session),
                                ) -> JSONResponse:
    try:
        for id_ in notific_data:
            id_int = int(id_)
            statement = update(orm.Notification).where(orm.Notification.id == id_int).values(is_checking=notific_data[id_])
            notif_results = await session.execute(statement)
        await session.commit()
    except Exception as e:
        logger.error(f"#Ошибка в функции update_notifications\nТекст ошибки: {e}")
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

@router.post("/update_time_last_in_wb/", status_code=status.HTTP_200_OK)    
async def update_time_last_in_wb(data: Dict,
                                 session: AsyncSession = Depends(orm.get_session),
                                ) -> bool:
    '''Функция обновляет время последнего заказа/продажи/воврата в БД
    '''
    try:
        subquery = select(orm.Notification.id).join(
            orm.WB,
            orm.WB.id == orm.Notification.wb_api_keys_id
        ).where(
            orm.Notification.type_operation_id == data['id_'],
            orm.WB.id == data['wb_api_keys_id']
        ).alias()

        # Формируем выражение SELECT для использования в клаузе IN
        # Возможно также понадобится использовать sclases подзапроса напрямую в IN, без дополнительного select
        ids_select = select(subquery.c.id)
        # Выполняем операцию UPDATE с условием WHERE на основе подзапроса
        statement = (
            update(orm.Notification).
            where(orm.Notification.id.in_(ids_select)).
            values(time_last_in_wb=datetime.datetime.fromisoformat(data['time_last_in']))
        )
        await session.execute(statement)
        await session.commit()
        return JSONResponse(content={
                            "status": "ok"
                            }
                            )
    except Exception as e:
        logger.error(f"#Ошибка в функции update_time_last_in_wb\nТекст ошибки: {e}")
        return JSONResponse(content={
                            "status": "error",
                            "text_error": e
                            }
                            )
  
@router.get("/get_time_last_in_wb/", status_code=status.HTTP_200_OK) 
async def get_time_last_in_wb(id_: int,
                              wb_api_keys_id: int,
                              session: AsyncSession = Depends(orm.get_session),
                              ) -> datetime.datetime:
    
    '''Функция возвращает время последнего обновления из БД для ключа :wb_api_keys_id: по операции с :id_: 
    '''
    try:
        statement = select(orm.Notification.time_last_in_wb)\
                                .join(orm.WB, orm.Notification.wb_api_keys_id == orm.WB.id)\
                                .where(orm.Notification.type_operation_id == id_,
                                   orm.WB.id == wb_api_keys_id)
        notif_results = await session.execute(statement)
        time_last_in_wb = notif_results.scalar()
    except Exception as e:
        logger.error(f"#Ошибка в функции get_time_last_in_wb\nТекст ошибки: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
                }
        )
    return JSONResponse(
        content={
            "status": "ok",
            "data": time_last_in_wb.isoformat() if time_last_in_wb is not None else time_last_in_wb
            }
    )