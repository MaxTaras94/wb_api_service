import asyncio
import aiohttp
from api.data_for_monitoring import OperationDataListResponse, OperationRegroupedDataResponse
from app.settings import settings
from app.logger import logger
from app.wb_monitoring.get_data_from_wb import (
        get_all_barcodes,
        get_data_from_wb,
        get_stocks_from_wb,
        parsing_order_data,
        parsing_sales_refunds_data
)
from api.notifications import update_time_last_in_wb
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
from typing import List, Tuple



async def get_subscribers() -> Tuple[OperationRegroupedDataResponse]:
    '''Функция возвращает список словарей пользователей, подписанных на получение уведомлений
    '''
    async with aiohttp.ClientSession() as client:      
        async with client.post(f"{settings.server_host}/api/monitoring/get_data/", json={'data':[1]}) as response_orders:
            users_subscribed_to_orders: OperationDataListResponse = await response_orders.json()
        async with client.post(f"{settings.server_host}/api/monitoring/get_data/", json={'data':[2,3]}) as response_sales_refunds:
            users_subscribed_sales_and_refunds: OperationDataListResponse = await response_sales_refunds.json()
    return users_subscribed_to_orders, users_subscribed_sales_and_refunds

async def process_get_data(url_for_req: str, 
                           subscription: OperationRegroupedDataResponse,
                           date_today: str
                           ) -> None:
    data_from_wb: List[dict] = await get_data_from_wb(url_for_req, 
                                                      subscription['api_key'],                                                
                                                      date_today
                                                      )
    try:
        all_barcodes: List[str] = get_all_barcodes(data_from_wb)
    except Exception as e:
        logger.error(e)                 
    # await asyncio.sleep(65)
    stocks_wb: List[dict] = await get_stocks_from_wb(settings.stockurl, 
                                                     subscription['api_key'],
                                                     date_today
                                                     )
    if 'orders' in url_for_req:
        parsing_data = await parsing_order_data([data_from_wb, stocks_wb], subscription)
    else:
        parsing_data = await parsing_sales_refunds_data([data_from_wb, stocks_wb], subscription)

async def check_orders(date_today: str):
    '''Функция для проверки заказов WB
    '''
    async with aiohttp.ClientSession() as client:      
        async with client.post(f"{settings.server_host}/api/monitoring/get_data/", json={'data':[1]}) as response_orders:
            users_subscribed_to_orders: OperationDataListResponse = await response_orders.json()# данные из БД о пользователях, которые подписаны на получаение уведомлений о Заказах
    tasks = []
    for subscription in users_subscribed_to_orders['data']:
        task = asyncio.create_task(process_get_data(settings.ordersurl, 
                                                    subscription,
                                                    date_today
                                                    ))
        tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=True)

async def check_sales_and_refunds(date_today: str):
    '''Функция для проверки продаж и возвратов WB
    '''
    async with aiohttp.ClientSession() as client: 
        async with client.post(f"{settings.server_host}/api/monitoring/get_data/", json={'data':[2,3]}) as response:
            users_subscribed_sales_and_refunds: OperationDataListResponse = await response.json() # данные из БД о пользователях, которые подписаны на получаение уведомлений о Продажах и Возвратах
    tasks = []
    for subscription in users_subscribed_sales_and_refunds:
        task = asyncio.create_task(process_get_data(settings.salesurl, 
                                                    subscription,
                                                    date_today
                                                    ))
        tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=True)


async def check_operations(today_date: str):
    pass
    
    
async def start_checking():
    today = datetime.datetime.today().strftime("%Y-%m-%d")
    await check_orders(today)
    await asyncio.sleep(500)
    await check_sales_and_refunds(today)        


if __name__ == "__main__":
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(start_checking, 'interval', minutes=30)
        scheduler.start()
    except Exception as e:
        logger.error(f'Ошибка в блоке __name__\nТекст ошибки: {e}')
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass