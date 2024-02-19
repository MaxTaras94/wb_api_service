import asyncio
import aiohttp
from api.data_for_monitoring import OperationDataListResponse
from app.settings import settings
from app.logger import logger
from app.wb_monitoring.get_data_from_wb import get_all_barcodes, get_data_from_wb, get_stocks_from_wb, parsing_order_data, parsing_sales_refunds_data
from api.notifications import update_time_last_in_wb
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import httpx

from typing import List



async def process_get_data(url_for_req: str, 
                           api_key_user: str,
                           id_wb_key: int,
                           name_key: str,
                           tg_user_id: int,
                           date_today: str,
                           flag: int) -> dict:
    data_from_wb: List[dict] = await get_data_from_wb(url_for_req, 
                                                api_key_user,                                                
                                                date_today,
                                                flag)
    try:
        all_barcodes: List[str] = get_all_barcodes(data_from_wb)
    except Exception as e:
        logger.error(e)                 
        return {'tg_user_id':tg_user_id, 'parsing_data': []} 
    await asyncio.sleep(65)
    stocks_wb: List[dict] = await get_stocks_from_wb(settings.stockurl, 
                                               api_key_user,
                                               date_today,
                                               flag)
    try:
        if 'orders' in url_for_req:
            parsing_data = await parsing_order_data([data_from_wb, stocks_wb], tg_user_id, api_key_user, id_wb_key, name_key)
        else:
            parsing_data = await parsing_sales_refunds_data([data_from_wb, stocks_wb], tg_user_id, api_key_user, id_wb_key, name_key)
        return {'tg_user_id':tg_user_id, 'parsing_data':parsing_data}     
    except Exception as e:
        logger.error(e)                 
        return {'tg_user_id':tg_user_id, 'parsing_data': []} 

async def check_orders(date_today: str):
    '''Функция для проверки заказов WB
    '''
    async with aiohttp.ClientSession() as client:      
        async with client.get(f"{settings.server_host}/api/monitoring/get_data/1/") as response_orders:
            users_subscribed_to_orders: OperationDataListResponse = await response_orders.json()# данные из БД о пользователях, которые подписаны на получаение уведомлений о Заказах
    tasks = []
    for user in users_subscribed_to_orders['data']:
        task = asyncio.create_task(process_get_data(settings.ordersurl, 
                                                    user["api_key"],
                                                    user["id"],
                                                    user['name_key'],
                                                    user["telegram_id"],
                                                    date_today,
                                                    0))
        tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=False)

async def check_sales_and_refunds(date_today: str):
    '''Функция для проверки продаж и возвратов WB
    '''
    async with aiohttp.ClientSession() as client: 
        async with client.get(f"{settings.server_host}/api/monitoring/get_data/2/") as response_sales:
            users_subscribed_to_sales: OperationDataListResponse = await response_sales.json() # данные из БД о пользователях, которые подписаны на получаение уведомлений о Продажах
        async with client.get(f"{settings.server_host}/api/monitoring/get_data/3/") as response_refunds:
            users_subscribed_to_refunds: OperationDataListResponse = await response_refunds.json()  # данные из БД о пользователях, которые подписаны на получаение уведомлений о Возвратах
    users_subscribed = []
    users_subscribed.extend(users_subscribed_to_sales["data"])
    users_subscribed.extend(users_subscribed_to_refunds["data"])
    unique_set = set((d["telegram_id"], d["api_key"], d["name_key"], d["id"]) for d in users_subscribed)
    result_list_users_subscribed = [dict(zip(["telegram_id", "api_key", "name_key",  "id"], t)) for t in unique_set]
    tasks = []
    for user in result_list_users_subscribed:
        task = asyncio.create_task(process_get_data(settings.salesurl, 
                                                    user["api_key"],
                                                    user["id"],
                                                    user['name_key'],
                                                    user["telegram_id"],
                                                    date_today,
                                                    0))
        tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=False)

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
        logger.error(e)
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass