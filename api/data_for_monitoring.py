from app.send_requests_to_tg import check_user_is_subscriber_channel
from app.settings import settings
import asyncio
import datetime
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import orm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Union
import time



class DataForMonitoring(BaseModel):
    ids_operations: List[int]
    ids_wb_key: List[int]
    names_wb_key: List[Optional[str]]
    telegram_ids: List[int]

    model_config = ConfigDict(from_attributes=True)
    
class OperationDataSimpleResponse(BaseModel):
    telegram_id: int
    type_operation: str
    id: int
    api_key: str
    name_key: Optional[str]
    is_checking: bool
    
    model_config = ConfigDict(from_attributes=True)
    
    
class OperationDataResponse(BaseModel):
    api_key: str
    ids_operations: List[int]
    ids_wb_key: List[int]
    names_wb_key: List[Optional[str]]
    telegram_ids: List[int]
    
    model_config = ConfigDict(from_attributes=True)

class OperationRegroupedDataResponse(BaseModel):
    api_key: str
    users: DataForMonitoring
    
    model_config = ConfigDict(from_attributes=True)

class OperationRegroupedDataListResponse(BaseModel):
    data: list[OperationRegroupedDataResponse]

class OperationDataListResponse(BaseModel):
    data: list[OperationDataResponse]

class OperationDataListSimpleResponse(BaseModel):
    data: list[OperationDataSimpleResponse]

router = APIRouter()


def regrouper_func(data: OperationDataListResponse,
                         is_checking_subscription: bool
                         ) -> OperationRegroupedDataListResponse:
    '''Функция для удобства работы с данными выполняет из перегруппировку и возвращает обратно
    '''   
    new_data = []
    cache = {}
    for d in data:
        result = {}        
        for i, operation_id in enumerate(d['ids_operations']):
            if operation_id not in result:
                result[operation_id] = {
                    'ids_wb_key': [],
                    'names_wb_key': [],
                    'telegram_ids': {}
                }
            result[operation_id]['ids_wb_key'].append(d['ids_wb_key'][i])
            result[operation_id]['names_wb_key'].append(d['names_wb_key'][i])
            if d['telegram_ids'][i] not in cache:
                if is_checking_subscription:
                    cache[d['telegram_ids'][i]] = check_user_is_subscriber_channel(d['telegram_ids'][i])
                else:
                    cache[d['telegram_ids'][i]] = None # это запись будет означать что мы не проверяли подписан ли пользователь на канал или нет
            result[operation_id]['telegram_ids'][d['telegram_ids'][i]] = {'is_subscriber': cache[d['telegram_ids'][i]]}
            time.sleep(0.05)
        new_data.append({"api_key": d['api_key'], "users": result})
    return new_data
    

@router.get("/get_data/{type_operation_id}/", response_model=OperationDataListSimpleResponse)
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
            OperationDataSimpleResponse.model_validate(u).model_dump() for u in data_for_monitoring
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

@router.post("/get_data_new/", response_model=OperationRegroupedDataListResponse)
async def get_data_for_all_users(data: Dict[str, List[int] | bool],
                                 session: AsyncSession = Depends(orm.get_session)
                                 ) -> JSONResponse:
    '''Функция возвращает из БД api ключи и всех пользователей, которые подписаны на уведомления с этим ключом по типу операций
        :type_operations_ids:
    '''
    try:
        operations_ids = data['operations']
        statement = select(
            orm.WB.api_key,
            func.array_agg(orm.TypeOperations.id).label('ids_operations'),
            func.array_agg(orm.WB.id).label('ids_wb_key'),
            func.array_agg(orm.WB.name_key).label('names_wb_key'),
            func.array_agg(orm.User.telegram_id).label('telegram_ids')
            ) \
            .join(orm.WB, orm.User.telegram_id == orm.WB.user_telegram_id) \
            .join(orm.Notification, orm.WB.id == orm.Notification.wb_api_keys_id) \
            .join(orm.TypeOperations, orm.Notification.type_operation_id == orm.TypeOperations.id) \
            .where(and_(orm.TypeOperations.id.in_(operations_ids), orm.Notification.is_checking == True)) \
            .group_by(orm.WB.api_key) \
            .order_by(orm.WB.api_key)
        results = await session.execute(statement)
        data_for_monitoring = results.all()
        response_data_intermediate = [
            OperationDataResponse.model_validate(u).model_dump() for u in data_for_monitoring
        ]
        response_data = regrouper_func(response_data_intermediate, data['is_checking_subscription'])
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