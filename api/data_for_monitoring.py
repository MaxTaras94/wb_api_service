from app.settings import settings
import datetime
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import orm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional




class OperationDataResponse(BaseModel):
    telegram_id: int
    type_operation: str
    id: int
    api_key: str
    name_key: Optional[str]
    is_checking: bool
    
    model_config = ConfigDict(from_attributes=True)


class OperationDataListResponse(BaseModel):
    data: list[OperationDataResponse]

class OperationDataResponseShort(BaseModel):
    telegram_ids: List[int]
    api_key: str
    type_operations: List[str]
    
    model_config = ConfigDict(from_attributes=True)


class OperationDataListShortResponse(BaseModel):
    data: list[OperationDataResponseShort]


router = APIRouter()


@router.get("/test/{tg_user_id}/", response_model=dict)
async def test(tg_user_id: int) -> JSONResponse:
    return JSONResponse(
    content={
        "status": "ok",
        "data": [{"ordersurl":settings.ordersurl,
                  "salesurl":settings.salesurl,
                  "stockurl":settings.salesurl,
                  "tg_sendmsg_url":settings.tg_sendmsg_url(user_id=tg_user_id, text_message="Test")}],
        }
    )

@router.get("/get_data/{type_operation_id}/", response_model=OperationDataListResponse)
async def get_data_api(type_operation_id: int, session: AsyncSession = Depends(orm.get_session)) -> JSONResponse:
    '''Функция возвращает из БД api ключи пользователей и типы операций, на которые они подписаны
    '''
    try:
        statement = select(orm.User.telegram_id,
                           orm.TypeOperations.type_operation,
                           orm.WB.id,
                           orm.WB.api_key,
                           orm.WB.name_key,
                           orm.Notification.is_checking) \
                            .join(orm.WB, orm.User.telegram_id == orm.WB.user_telegram_id) \
                            .join(orm.Notification, orm.WB.id == orm.Notification.wb_api_keys_id) \
                            .join(orm.TypeOperations, orm.Notification.type_operation_id == orm.TypeOperations.id) \
                            .where(and_(orm.TypeOperations.id == type_operation_id, orm.Notification.is_checking == True)) \
                            .order_by(orm.User.telegram_id)
        results = await session.execute(statement)
        data_for_monitoring = results.all()
        response_data = [
            OperationDataResponse.model_validate(u).model_dump() for u in data_for_monitoring
        ]
        return JSONResponse(
        content={
            "status": "ok",
            "data": response_data,
        }
    )
    except Exception as e:
        return JSONResponse(
        content={
            "status": "error",
            "data": [{"text_error": e}],
        }
    )

@router.get("/get_data_for_all_users/", response_model=OperationDataListShortResponse)
async def get_data_for_all_users(session: AsyncSession = Depends(orm.get_session)) -> JSONResponse:
    '''Функция возвращает из БД api ключи пользователей и типы операций, на которые они подписаны
    '''
    try:
        statement = select(
            orm.WB.api_key,
            func.array_agg(func.distinct(orm.User.telegram_id)).label('telegram_ids'),  # Агрегируем telegram_id в список, оставляя только уникальные
            func.array_agg(func.distinct(orm.TypeOperations.type_operation)).label('type_operations')  # Агрегируем type_operation в список, оставляя только уникальные
            ) \
            .join(orm.WB, orm.User.telegram_id == orm.WB.user_telegram_id) \
            .join(orm.Notification, orm.WB.id == orm.Notification.wb_api_keys_id) \
            .join(orm.TypeOperations, orm.Notification.type_operation_id == orm.TypeOperations.id) \
            .where(orm.Notification.is_checking == True) \
            .group_by(orm.WB.api_key) \
            .order_by(orm.WB.api_key)

        results = await session.execute(statement)
        data_for_monitoring = results.all()
        response_data = [
            OperationDataResponseShort.model_validate(u).model_dump() for u in data_for_monitoring
        ]
        return JSONResponse(
        content={
            "status": "ok",
            "data": response_data,
        }
    )
    except Exception as e:
        return JSONResponse(
        content={
            "status": "error",
            "data": [{"text_error": e}],
        }
    )