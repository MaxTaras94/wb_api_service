import asyncio
from api.data_for_monitoring import OperationDataListResponse, OperationRegroupedDataResponse
from app.send_requests_to_tg import check_user_is_subscriber_channel
from app.settings import settings
from app.logger import logger
from app.wb_monitoring.get_data_from_wb_new import (
        get_data_from_wb,
        get_stocks_from_wb,
        parsing_order_data,
        parsing_sales_refunds_data
)
from api.notifications import update_time_last_in_wb
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import httpx
import itertools
from typing import List, Tuple


async def is_checking_subscription() -> bool:
    '''Функция возвращает из БД False, если проверка подписки не активна, иначе вернёт True
    '''
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            check_subscription = await client.get(settings.server_host+"/api/botsettings/get_status_check_subscription/")
        data =  check_subscription.json()
        return data['is_checking']
    except Exception as e:
        return {'status': 'error', 'text_error': e, 'is_checking': None}
        
        
async def get_subscribers(checking_subscription: bool) -> Tuple[OperationRegroupedDataResponse]:
    '''Функция возвращает список словарей пользователей, подписанных на получение уведомлений
    '''
    async with httpx.AsyncClient(timeout=30) as client:     
        response = await client.post(f"{settings.server_host}/api/monitoring/get_data_new/", json={'operations': [1,2,3], 
                                                                                             'is_checking_subscription': checking_subscription
                                                                                             }
                                                                                             )
    users_subscribed_to_opearations: OperationRegroupedDataResponse = response.json()
    return users_subscribed_to_opearations['data']

async def process_get_data(url_for_req: str,
                           stocks_wb: List[dict],
                           subscription: OperationRegroupedDataResponse,
                           date_today: str
                           ) -> None:
    '''В этой функции получается инфа от ВБ и отправляется на парсинг в соответствующие ф-ции, в зависимости от типа операции
    '''
    data_from_wb: List[dict] = await get_data_from_wb(url_for_req, 
                                                      subscription['api_key'],                                                
                                                      date_today
                                                      )
    if isinstance(data_from_wb, list):
        if 'orders' in url_for_req:
            parsing_data = await parsing_order_data([data_from_wb, stocks_wb], subscription)
        else:
            parsing_data = await parsing_sales_refunds_data([data_from_wb, stocks_wb], subscription)
    else:
        logger.error(f"Ошибка при получении данных о {url_for_req.split('/')[-1]}: {data_from_wb}")
        
        
def create_task_list(stocks_wb: List[dict],
                     subscription: OperationRegroupedDataResponse,
                     date_today: str) -> list:
    '''Формируем список задач для параллельной проверки
       1 - Заказ
       2 - Продажа
       3 - Возврат
    '''
    tasks = []
    oparations = subscription['users'].keys()
    if '1' not in oparations:
        task = asyncio.create_task(process_get_data(settings.salesurl, stocks_wb, subscription, date_today))
    elif '2' not in oparations and '3' not in oparations:
        task = asyncio.create_task(process_get_data(settings.ordersurl, stocks_wb, subscription, date_today))
    else:
        task = asyncio.create_task(process_get_data(settings.ordersurl, stocks_wb, subscription, date_today))
        task_1 = asyncio.create_task(process_get_data(settings.salesurl, stocks_wb, subscription, date_today))
        tasks.append(task_1)
    tasks.append(task)
    return tasks

async def try_to_get_stocks(subscription: OperationRegroupedDataResponse,
                            date_today: str
                            ) -> List[dict]:
    '''Функция для получения остатков со складов ВБ. Она нужна для повторения попыток получить остатки, если с первого раза ВБ вернул ошибку
    '''
    count_try = 4
    num = 0
    while num <= count_try:
        stocks_wb = await get_stocks_from_wb(settings.stockurl, subscription['api_key'], date_today)
        if isinstance(stocks_wb, dict):
            num += 1
            await asyncio.sleep(10)
            continue
        else:
            break
    return stocks_wb
    
async def check_operations(date_today: str):
    
    checking_subscription: bool = await is_checking_subscription()
    subscribers: OperationRegroupedDataResponse = await get_subscribers(checking_subscription)
    tasks = []
    for subscription in subscribers:
        if checking_subscription:
            user_is_subscriber_channel = list(itertools.chain.from_iterable([[subscription['users'][key]['telegram_ids'][k]['is_subscriber'] for k in \
            subscription['users'][key]['telegram_ids'].keys()] for key in subscription['users'].keys()])) #получаем список значений по ключу is_subscriber для каждого tg id из списка
            if any(user_is_subscriber_channel): #проверяем есть ли пользователи подписанные на канал
                # stocks_wb: List[dict] = await try_to_get_stocks(subscription['api_key'], date_today)
                stocks_wb = await get_stocks_from_wb(settings.stockurl, subscription['api_key'], date_today)
                tasks.extend(create_task_list(stocks_wb, subscription, date_today))
            else:
                continue
        else:
            # stocks_wb: List[dict] = await try_to_get_stocks(subscription['api_key'], date_today)
            stocks_wb = await get_stocks_from_wb(settings.stockurl, subscription['api_key'], date_today)
            tasks.extend(create_task_list(stocks_wb, subscription, date_today))
    await asyncio.gather(*tasks, return_exceptions=True)

async def start_checking():
    today = datetime.datetime.today().strftime("%Y-%m-%d")
    await check_operations(today)


if __name__ == "__main__":
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(start_checking, 'interval', minutes=3)
        scheduler.start()
    except Exception as e:
        logger.error(f'Ошибка в блоке __name__\nТекст ошибки: {e}')
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass