import asyncio
from api.data_for_monitoring import OperationDataListResponse, OperationRegroupedDataResponse
from app.settings import settings
from app.logger import logger
from app.wb_monitoring.get_data_from_wb import (
        get_data_from_wb,
        get_stocks_from_wb,
        parsing_order_data,
        parsing_sales_refunds_data,
        sender_messeges_to_telegram,
        total_counter_for_proxies
)
from api.notifications import update_time_last_in_wb
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import httpx
import itertools
import math
import requests
from typing import List, Tuple
import time



def is_checking_subscription() -> bool:
    '''Функция возвращает из БД False, если проверка подписки не активна, иначе вернёт True
    '''
    try:
        check_subscription = requests.get(settings.server_host+"/api/botsettings/get_status_check_subscription/")
        data =  check_subscription.json()
        return data['is_checking']
    except Exception:
        import traceback
        logger.error(traceback.format_exc())
        return None
        
def try_to_get_stocks(api_key: str) -> List[dict]:
    '''Функция для получения остатков со складов ВБ. Она нужна для повторения попыток получить остатки, если с первого раза ВБ вернул ошибку
    '''
    count_try = 4
    num = 0
    while num <= count_try:
        stocks_wb = get_stocks_from_wb(api_key)
        if isinstance(stocks_wb, dict):
            num += 1
        else:
            break
    return stocks_wb

def try_to_get_data_from_wb(url_for_req: str,
                                  api_key: str
                                  ) -> List[dict]:
    '''Функция для получения данных по операциям  ВБ. Она нужна для повторения попыток получить данные, если с первого раза ВБ вернул ошибку
    '''
    count_try = 4
    num = 0
    while num <= count_try:
        data_from_wb = get_data_from_wb(url_for_req, api_key)
        if isinstance(data_from_wb, dict):
            num += 1
        else:
            break
    return data_from_wb
    
def get_subscribers(checking_subscription: bool) -> Tuple[OperationRegroupedDataResponse]:
    '''Функция возвращает список словарей пользователей, подписанных на получение уведомлений
    '''
    response = requests.post(f"{settings.server_host}/api/monitoring/get_data_new/", json={'operations': [1,2,3], 
                                                                                                   'is_checking_subscription': checking_subscription
                                                                                                   }
                                    )
    users_subscribed_to_opearations: OperationRegroupedDataResponse = response.json()
    return users_subscribed_to_opearations['data']

def process_get_data(url_for_req: str,
                           stocks_wb: List[dict],
                           subscription: OperationRegroupedDataResponse
                           ) -> None:
    '''В этой функции получается инфа от ВБ и отправляется на парсинг в соответствующие ф-ции, в зависимости от типа операции
    '''
    data_from_wb: List[dict] = try_to_get_data_from_wb(url_for_req, 
                                                          subscription['api_key']
                                                          )
    if all([isinstance(data_from_wb, list), isinstance(stocks_wb, list)]):
        if 'orders' in url_for_req:
            parsing_data = parsing_order_data([data_from_wb, stocks_wb], subscription)
        else:
            parsing_data = parsing_sales_refunds_data([data_from_wb, stocks_wb], subscription)
    else:
        logger.error(f"FUNC process_get_data Ошибка при получении данных {url_for_req}: {data_from_wb} \n stocks_wb ={stocks_wb} \n Ключ {subscription['api_key']}")
        
        
def create_task_list(stocks_wb: List[dict],
                     subscription: OperationRegroupedDataResponse) -> list:
    '''Формируем список задач для параллельной проверки
       1 - Заказ
       2 - Продажа
       3 - Возврат
    '''
    tasks = []
    oparations = subscription['users'].keys()
    if '1' not in oparations:
        task = asyncio.create_task(process_get_data(settings.salesurl, stocks_wb, subscription))
    elif '2' not in oparations and '3' not in oparations:
        task = asyncio.create_task(process_get_data(settings.ordersurl, stocks_wb, subscription))
    else:
        task = asyncio.create_task(process_get_data(settings.ordersurl, stocks_wb, subscription))
        task_1 = asyncio.create_task(process_get_data(settings.salesurl, stocks_wb, subscription))
        tasks.append(task_1)
    tasks.append(task)
    return tasks
    
async def check_operations() -> None:
    '''Функция запускает проверку операций на ВБ по расписанию
    '''
    logger.info(f'total_counter_for_proxies = {total_counter_for_proxies}')
    checking_subscription: bool = is_checking_subscription()
    start_time = time.time()
    subscribers: OperationRegroupedDataResponse = get_subscribers(checking_subscription)
    end_time = time.time()
    execution_time_of_get_subscribers = end_time - start_time
    logger.info(f'Время выполнения ф-ции get_subscribers = {math.ceil(execution_time_of_get_subscribers)} sec. Проверил статус для {len(subscribers)} users')
    tasks = []
    for subscription in subscribers:
        if checking_subscription:
            user_is_subscriber_channel = list(itertools.chain.from_iterable([[subscription['users'][key]['telegram_ids'][k]['is_subscriber'] for k in \
            subscription['users'][key]['telegram_ids'].keys()] for key in subscription['users'].keys()])) #получаем список значений по ключу is_subscriber для каждого tg id из списка
            logger.info(f'В ф-ции check_operations. user_is_subscriber_channel = {user_is_subscriber_channel}')
            if any(user_is_subscriber_channel): #проверяем есть ли пользователи подписанные на канал
                stocks_wb = try_to_get_stocks(subscription['api_key'])
                tasks.extend(create_task_list(stocks_wb, subscription))
            else:
                sender_messeges_to_telegram({}, subscription, "1")
        else:
            stocks_wb = try_to_get_stocks(subscription['api_key'])
            tasks.extend(create_task_list(stocks_wb, subscription))
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(check_operations, 'interval', minutes=3)
        scheduler.start()
    except Exception:
        import traceback
        logger.error(traceback.format_exc())
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass