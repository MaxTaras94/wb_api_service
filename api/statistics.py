from app.logger import logger
from app.wb_monitoring.get_data_from_wb_new import get_data_from_wb
from app.settings import settings
import datetime
import math
import orm
from typing import List
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



router = APIRouter()

    

@router.get("/get_statistics/")
async def get_statistics(user_telegram_id: int, 
                         key_id: int,
                         session: AsyncSession = Depends(orm.get_session)
                         ) -> JSONResponse:
    
    logger.info(f"Вызов метода get_statistics. Время {datetime.datetime.today().strftime('%d.%m.%Y %H:%M:%S')} Переданы параметры: user_telegram_id={user_telegram_id}; key_id={key_id}")
    statement = select(orm.WB.api_key).where(orm.WB.id == key_id,
                                             orm.WB.user_telegram_id == user_telegram_id)
    results = await session.execute(statement)
    api_key = results.scalar()
    date_today = datetime.datetime.today()
    date_and_time_yestarday = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    orders: List[dict] = await get_data_from_wb(settings.ordersurl, 
                                                api_key,
                                                date_and_time_yestarday)
    sales_and_refunds: List[dict] = await get_data_from_wb(settings.salesurl, 
                                                           api_key,
                                                           date_and_time_yestarday)
    try:
        response_data = [{
                      "orders": math.ceil(sum([1 for _ in orders if not _["isCancel"] and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()])),
                      "sum_orders": math.ceil(sum([_["finishedPrice"] for _ in orders if not _["isCancel"] and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()])),
                      "sales": math.ceil(sum([1 for _ in sales_and_refunds if _["saleID"][0] == "S" and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()])),
                      "sum_sales": math.ceil(sum([_["finishedPrice"] for _ in sales_and_refunds if _["saleID"][0] == "S" and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()])),
                      "refunds": math.ceil(sum([1 for _ in sales_and_refunds if _["saleID"][0] == "R" and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()])),
                      "sum_refunds": math.ceil(sum([_["finishedPrice"] for _ in sales_and_refunds if _["saleID"][0] == "R" and \
                      datetime.datetime.fromisoformat(_['date']).date() == date_today.date()]))
                      }
                    ]
        return JSONResponse(
            content={
                "status": "ok",
                "data": response_data
            }
        )
    except TypeError:
        return JSONResponse(
        content={
            "status": "error",
            "data": "WB вернул ошибку, попробуйте позже("
        }
    )
    