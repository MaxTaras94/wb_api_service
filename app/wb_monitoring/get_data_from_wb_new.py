import asyncio
from app.logger import logger
from api.data_for_monitoring import OperationRegroupedDataResponse
from api.notifications import update_time_last_in_wb, get_time_last_in_wb
from app.digit_separator import digit_separator
from app.settings import settings
from app.send_requests_to_tg import send_message_to_tg
from app.templates.templates import render_template
from collections import defaultdict
import datetime
import httpx
import math
from random import random, randint
from typing import Dict, List, Tuple
import urllib.request
from urllib.parse import quote



def get_all_barcodes(operations: List[dict]) -> List[str]:
    '''Функция возвращает список уникальных bar-кодов по полученному списку заказов/продаж/возвратов
    '''
    return list(set([_["barcode"] for _ in operations]))

def get_count_of_operations_for_barcode(operations: List[dict]
                                        ) -> List[dict]:
    list_of_barcodes: List[str] = get_all_barcodes(operations)
    barcodes_and_count_of_operations = {}
    for barcode in list_of_barcodes:
        barcodes_and_count_of_operations[barcode] = math.ceil(sum([1 for _ in operations if _['barcode'] == barcode]) / 7)
    for o in operations:
        o["count_of_operations"] = barcodes_and_count_of_operations[o['barcode']]
    return operations
    
async def dynamics_operations_on_barcodes(operations: List[dict],
                                          list_of_warehouses: List[dict],
                                          api_key: str
                                          ) -> Dict[str, int]:
    '''Функция обогащает данные об операциях данными о статистике этих самых операций за последие 7 ней + данными об FBS остатках, если селлер работает по такой модели
    '''
    for num, warehouse in enumerate(list_of_warehouses):
        all_warehouse_stocks = await get_all_warehouse_stocks(api_key, warehouse['id'], get_all_barcodes(operations))
        list_of_warehouses[num]['stocks'] = {item['sku']: item['amount'] for item in all_warehouse_stocks['stocks']}  
    for o in operations:
        o['stocks_on_warehouses'] = []
        for num, stock_warehouse in enumerate(list_of_warehouses):
            on_count_days = stock_warehouse['stocks'][o['barcode']] / o["count_of_operations"]
            on_count_days_floor = math.floor(on_count_days) if on_count_days > 1 else 0
            o['stocks_on_warehouses'].append({"warehouse_name": stock_warehouse['name'],
                                              "stock": stock_warehouse['stocks'][o['barcode']],
                                              "on_count_days": on_count_days_floor
                                             })
            
        o['total_stocks_on_warehouses'] = sum([_["stock"] for _ in o['stocks_on_warehouses']])
    return operations

def operations_sorter(operations: List[dict]) -> List[dict]:
    '''Функция на вход получает данные из API WB о заказах/возвратах/продажах
       Добавляет в данные дату по каждой операции в формате datetime.datetime,
       сортирует и возращает их обратно
    '''
    parsed_operations = []
    for operation in operations:
        operation['parsed_date'] = datetime.datetime.fromisoformat(operation["date"])
        parsed_operations.append(operation)
    return sorted(parsed_operations, key=lambda d: d["parsed_date"])

async def get_all_warehouse_stocks(api_key: str,
                                   warehouseId: int,
                                   barcodes: List[str]
                                   ) -> List[dict]:
    '''Функция возвращает остатки товаров со склада продавца по его warehouseId для переданных barcodes
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        warehouse_stocks = await client.post(settings.warehouses_stocks+'/'+str(warehouseId), headers=headers, json={'skus':barcodes})
    return warehouse_stocks.json()


async def get_all_warehouses(api_key: str) -> List[dict]:
    '''Функция возвращает список всех пользовательских складов
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        warehouses = await client.get(settings.warehouses, headers=headers)
    if warehouses.status_code != 200:        
        return "error"
    else:
        return warehouses.json()
        
async def get_data_from_wb(link_operation_wb: str,
                           api_key: str) -> List[dict]:
    '''Функция возвращает данные о заказах/продажах/возвратах из API WB 
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    date_and_time = (datetime.datetime.today() - datetime.timedelta(days=8)).strftime("%Y-%m-%d")
    api_url_yestarday = link_operation_wb+"?dateFrom="+date_and_time
    async with httpx.AsyncClient(timeout=30) as client:
       wb_data = await client.get(api_url_yestarday, headers=headers)
    operations = wb_data.json()
    if isinstance(operations, list):
        operation_with_dynamics = get_count_of_operations_for_barcode(operations)
        all_warehouses = await get_all_warehouses(api_key)
        if all_warehouses == "error":    
            return operation_with_dynamics
        else:
            upgrade_operations = await dynamics_operations_on_barcodes(operation_with_dynamics, all_warehouses, api_key) #обогащаем операции данными об остатках со складов селлера
            return upgrade_operations
    return operations
    
async def get_stocks_from_wb(api_key: str) -> List[dict]:
    '''Функция возвращает данные об остатках из API WB 
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    date_and_time = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    api_url_stocks = settings.stockurl+"?dateFrom="+date_and_time
    async with httpx.AsyncClient(timeout=30) as client:
        stocks = await client.get(api_url_stocks, headers=headers)
    return stocks.json()
        
        
async def update_status_subscribe_in_db(tg_user_id: int,
                                        is_subscriber: bool
                                        ) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        await client.post(settings.server_host + f"/api/checksubscribe/update_status_subscription/",
                          json={'tg_user_id': tg_user_id,
                                'is_subscriber': is_subscriber
                               }
                          ) 

async def sender_messeges_to_telegram(data_for_msg: dict,
                                      subscription: OperationRegroupedDataResponse,
                                      type_operation: str = None
                                      ) -> bool:   
    try:
        name_template = 'msg_with_orders_for_client.j2' if type_operation == "1" else "msg_with_sales_and_refunds_for_client.j2"
        telegram_ids = list(subscription['users'][type_operation]['telegram_ids'].keys())
        for num, tg_user_id in enumerate(telegram_ids):
            is_subscriber = subscription['users'][type_operation]['telegram_ids'][tg_user_id]['is_subscriber']
            async with httpx.AsyncClient(timeout=120) as client:
                data = await client.get(settings.server_host + f"/api/checksubscribe/get_current_status/{tg_user_id}")
            is_subscriber_db = data.json()
            logger.info(f"subscription['api_key'] = {subscription['api_key']}\nis_subscriber = {is_subscriber} | is_subscriber_db = {is_subscriber_db} ")
            if is_subscriber or is_subscriber is None:
                name_key = subscription['users'][type_operation]['names_wb_key'][num]
                data_for_msg['name_key'] = name_key if name_key is not None else subscription['api_key'][:10]+"..."+subscription['api_key'][-10:]
                text_msg = render_template(name_template, data={'data':data_for_msg, 'quote':quote, 'len': len})
                status_sending = await send_message_to_tg(tg_user_id, text_msg, data_for_msg['img'])
                if not is_subscriber_db["is_subscriber"]:
                    await update_status_subscribe_in_db(tg_user_id, True)
            else:
                if is_subscriber_db["is_subscriber"]:
                    text_msg = render_template("no_send_alert_of_new_operations.j2")
                    status_sending = await send_message_to_tg(tg_user_id, text_msg, "")
                    await update_status_subscribe_in_db(tg_user_id, False) 
            logger.info(f"Статус отправки сообщения в тг, ф-ция sender_messeges_to_telegram:  {status_sending}")
        await asyncio.sleep(0.1)
        return True
    except Exception:
        import traceback
        logger.error(traceback.format_exc())
        return False

async def generic_link_for_nmId_img(nmId: int) -> str:
    '''Функция на вход получает артикул товара WB :nmId: и возвращает ссылку на картинку для этого артикула
    '''
    nmId_str = str(nmId)
    if len(nmId_str) > 9 or len(nmId_str) < 8:
        return ""
    for n in range(1, 15):
        N = "0"+str(n) if n < 10 else str(n)
        if len(nmId_str) == 9:
            photo_url = f'https://basket-{N}.wb.ru/vol{nmId_str[0:4]}/part{nmId_str[0:6]}/{nmId_str}/images/big/1.webp'
        elif len(nmId_str) == 8:
            photo_url = f'https://basket-{N}.wb.ru/vol{nmId_str[0:3]}/part{nmId_str[0:5]}/{nmId_str}/images/big/1.webp'            
        async with httpx.AsyncClient(timeout=30) as client:
            img_res = await client.get(photo_url)
        status_code = img_res.status_code
        if status_code == 200:
            return photo_url
        else:
            continue
    else:
        return ""

async def get_last_time_operation(id_:int,
                                  id_wb_key: int,
                                  date_today: datetime.datetime
                                  ) -> datetime.datetime:
    '''Функция возвращает из БД время последней операции в WB 
    '''
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.get(f'{settings.server_host}/api/notifications/get_time_last_in_wb/?id_={id_}&wb_api_keys_id={id_wb_key}')
    time_last_operation = res.json()
    time_last_operation = datetime.datetime.fromisoformat(time_last_operation['data']) if time_last_operation['data'] is not None \
    else datetime.datetime.today() - datetime.timedelta(minutes=40)
    return time_last_operation


async def update_time_last_in_wb(id_operation: int,
                                 id_wb_key: int,
                                 date_and_time_operation: str
                                 ) -> None:
    '''Функция обновляет данные в БД по последней операции
    '''
    async with httpx.AsyncClient(timeout=120) as client:
        await client.post(f'{settings.server_host}/api/notifications/update_time_last_in_wb/',
                           json={'id_':id_operation,
                                       'wb_api_keys_id':id_wb_key,
                                       'time_last_in':date_and_time_operation
                                }
                         )

async def get_feedback_and_rating(nmId: int) -> tuple:
    '''Функция возвращает данные отзывы и рейтинг для артикула :nmId:
    '''
    api_url = f"https://card.wb.ru/cards/detail?curr=rub&dest=123585628&nm={nmId}" # ссыль для получения данных о кол-ве отзывов и рейтинге для nmId
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(api_url)
        response = res.json()
        data = response["data"]["products"][0]
        return data["feedbacks"], data["reviewRating"]
    except:
        return "-", "-"
 

def get_unique_warehouesa_stock(stocks_for_nmId: List[dict]) -> List[dict]:
    '''Функция на вход получает список словарей с данными по складам для конкертного артикула. Возвращает самый актуальный список уникальных складов по последней дату обновления
    '''
    unique_dict = defaultdict(dict)
    for d in stocks_for_nmId:
        wh_name = d['warehouseName']
        if wh_name not in unique_dict or d['lastChangeDate'] > unique_dict[wh_name]['lastChangeDate']:
            unique_dict[wh_name] = d
    return list(unique_dict.values())                    

async def parsing_order_data(orders_from_wb: List[List[dict]],
                             subscription: OperationRegroupedDataResponse
                             ) -> None:
    '''Функция на вход получает ответ от API WB о заказах
       Парсит ответ и рассылает пользователям в тг
    '''
    date_today_str = datetime.datetime.today().strftime("%Y-%m-%d")
    date_today = datetime.datetime.strptime(date_today_str, "%Y-%m-%d") 
    time_last_order_in_wb_from_db = await get_last_time_operation(1, subscription['users']['1']['ids_wb_key'][0], date_today)
    stocks = orders_from_wb[1]
    orders = operations_sorter(orders_from_wb[0])
    time_last_order_in_wb = time_last_order_in_wb_from_db
    status_send_msg_in_tg = None
    try:
        for order in orders:
            date_and_time_order = order['parsed_date']
            if not order["isCancel"]:  
                if date_and_time_order > time_last_order_in_wb_from_db and date_and_time_order.date() >= date_today.date():
                    stocks_for_nmId_order = [_ for _ in stocks if _['nmId'] == order["nmId"]]
                    unique_stocks = get_unique_warehouesa_stock(stocks_for_nmId_order)
                    time_last_order_in_wb = date_and_time_order
                    feedbacks, reviewRating = await get_feedback_and_rating(order["nmId"])
                    img_link = await generic_link_for_nmId_img(order["nmId"])
                    stocks_on_warehouses = order.get('stocks_on_warehouses', [])
                    in_way_to_client = 0
                    in_way_from_client = 0
                    if isinstance(stocks, list):
                        for stock in unique_stocks:
                            if stock["quantityFull"] > 0:
                                in_way_to_client += stock["inWayToClient"]
                                in_way_from_client += stock["inWayFromClient"]
                                if stock["quantityFull"] < order["count_of_operations"]:
                                    on_count_days = 0
                                else:
                                    on_count_days = math.floor(stock["quantityFull"] / order["count_of_operations"])
                                stocks_on_warehouses.append({"warehouse_name": stock["warehouseName"],
                                                              "stock": stock["quantityFull"],
                                                              "on_count_days": on_count_days
                                                             })
                    total_stocks_on_warehouses = sum([_["stock"] for _ in stocks_on_warehouses])
                    data_for_msg = {
                        "date_and_time_order": date_and_time_order.strftime("%d.%m.%Y %H:%M:%S"),
                        "number_orders_with_this_nmId_today": digit_separator(math.ceil(sum([1 for _ in orders if all([_["nmId"] == order["nmId"], \
                        _["parsed_date"].date() == date_today.date(), _["parsed_date"].time() <= date_and_time_order.time()])]))),
                        "number_orders_with_this_nmId_yesterday": digit_separator(math.ceil(sum([1 for _ in orders if all([_["nmId"] == order["nmId"], \
                        _["parsed_date"].date().day == (date_today.date().day - 1), _["parsed_date"].date().day > (date_today.date().day - 2)])]))),
                        "total_count_orders_today": digit_separator(math.ceil(sum([1 for _ in orders if _["parsed_date"].date() == date_today.date() \
                        and _["parsed_date"].time() <= date_and_time_order.time()]))),
                        "total_sum_orders_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        _["parsed_date"].date() == date_today.date() and _["parsed_date"].time() <= date_and_time_order.time()]))),
                        "total_sum_orders_with_this_nmId_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        all([_["nmId"] == order["nmId"], _["parsed_date"].date() == date_today.date(), _["parsed_date"].time() <= date_and_time_order.time()])]))),
                        "total_sum_orders_with_this_nmId_yesterday": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        all([_["nmId"] == order["nmId"], _["parsed_date"].date().day == (date_today.date().day - 1), _["parsed_date"].date().day > \
                        (date_today.date().day - 2)])]))),
                        "spp_percent": order["spp"],
                        "spp_sum": digit_separator(math.ceil((order["spp"]*order["priceWithDisc"])/100)),
                        "img": img_link,
                        "finishedPrice": digit_separator(math.ceil(order["finishedPrice"])),
                        "nmId": order["nmId"],
                        "techSize": order["techSize"],
                        "subject": order["subject"],
                        "brand": order["brand"],
                        "supplierArticle": order["supplierArticle"],
                        "typeOperation": "Заказ",
                        "feedbacks": feedbacks,
                        "reviewRating": reviewRating,
                        "warehouseName": order['warehouseName'] + " → " + order['regionName'],
                        "stocks_on_warehouses": stocks_on_warehouses,
                        "total_stocks_on_warehouses": total_stocks_on_warehouses,
                        "inWayToClient": digit_separator(in_way_to_client),
                        "inWayFromClient": digit_separator(in_way_from_client)
                    }    
                    status_send_msg_in_tg = await sender_messeges_to_telegram(data_for_msg, subscription, type_operation = '1')
        if status_send_msg_in_tg:
            for id_wb_key in subscription['users']['1']['ids_wb_key']:           
                await update_time_last_in_wb(1, id_wb_key, time_last_order_in_wb.isoformat())
    except Exception:
        import traceback
        logger.error(traceback.format_exc())


async def parsing_sales_refunds_data(operations_from_wb: List[List[dict]],
                                     subscription: OperationRegroupedDataResponse
                                     ) -> None:
    '''Функция на вход получает ответ от API WB о продажах или возвратах.
       Превращает в словарь с нужными полями, передает словарь в рендер jinja2 и после ф-цию отправки соощбений в бота тг
    '''
    date_today_str = datetime.datetime.today().strftime("%Y-%m-%d")
    date_today = datetime.datetime.strptime(date_today_str, "%Y-%m-%d")
    time_last_sale_in_wb_from_db = await get_last_time_operation(2, subscription['users']['2']['ids_wb_key'][0], date_today)
    time_last_refund_in_wb_from_db = await get_last_time_operation(3, subscription['users']['3']['ids_wb_key'][0], date_today)
    stocks = operations_from_wb[1]
    operations = operations_sorter(operations_from_wb[0])
    time_last_sale_in_wb = time_last_sale_in_wb_from_db
    time_last_refund_in_wb = time_last_refund_in_wb_from_db
    status_send_msg_sell_in_tg = None
    status_send_msg_ref_in_tg = None
    try:
        for operation in operations:
            date_and_time_operation = operation["parsed_date"]
            if date_and_time_operation.date() >= date_today.date():
                if operation["saleID"][0] == "S" and date_and_time_operation > time_last_sale_in_wb_from_db or operation["saleID"][0] == "R" and \
                date_and_time_operation > time_last_refund_in_wb_from_db:
                    stocks_for_nmId_operation = [_ for _ in stocks if _['nmId'] == operation["nmId"]]
                    unique_stocks = get_unique_warehouesa_stock(stocks_for_nmId_operation)
                    feedbacks, reviewRating = await get_feedback_and_rating(operation["nmId"])
                    img_link = await generic_link_for_nmId_img(operation["nmId"])
                    time_last_sale_in_wb = date_and_time_operation if operation["saleID"][0] == "S" else time_last_sale_in_wb_from_db
                    time_last_refund_in_wb = date_and_time_operation if operation["saleID"][0] == "R" else time_last_refund_in_wb_from_db
                    stocks_on_warehouses = operation.get('stocks_on_warehouses', [])
                    in_way_to_client = 0
                    in_way_from_client = 0
                    if isinstance(stocks, list):
                        for stock in unique_stocks:
                            if stock["nmId"] == operation["nmId"] and stock["quantityFull"] > 0:
                                in_way_to_client += stock["inWayToClient"]
                                in_way_from_client += stock["inWayFromClient"]
                                if stock["quantityFull"] < operation["count_of_operations"]:
                                    on_count_days = 0
                                else:
                                    on_count_days = math.floor(stock["quantityFull"] / operation["count_of_operations"])
                                stocks_on_warehouses.append({"warehouse_name": stock["warehouseName"],
                                                              "stock": stock["quantityFull"],
                                                              "on_count_days": on_count_days
                                                             })
                    total_stocks_on_warehouses = sum([_["stock"] for _ in stocks_on_warehouses])
                    data_for_msg = {
                        "date_and_time_operation": date_and_time_operation.strftime("%d.%m.%Y %H:%M:%S"),
                        "number_operations_with_this_nmId_today": digit_separator(math.ceil(sum([1 for _ in operations if _["nmId"] == operation["nmId"] \
                        and all([_["saleID"][0] == operation["saleID"][0], _["parsed_date"].time() <= date_and_time_operation.time(),\
                        _["parsed_date"].date() == date_today.date()])]))),
                        "total_sum_operations_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations if all([_["saleID"][0] == operation["saleID"][0],\
                        _["parsed_date"].time() <= date_and_time_operation.time(), _["parsed_date"].date() == date_today.date()])]))),
                        "total_sum_operations_with_this_nmId_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations \
                        if all([_["nmId"] == operation["nmId"], _["saleID"][0] == operation["saleID"][0], \
                        _["parsed_date"].time() <= date_and_time_operation.time(), _["parsed_date"].date() == date_today.date()])]))),
                        "total_count_operations_today": digit_separator(math.ceil(sum([1 for _ in operations if all([_["saleID"][0] == operation["saleID"][0],\
                        _["parsed_date"].time() <= date_and_time_operation.time(), _["parsed_date"].date() == date_today.date()])]))),
                        "number_operations_with_this_nmId_yesterday": digit_separator(math.ceil(sum([1 for _ in operations if all([_["nmId"] == operation["nmId"], \
                        _["saleID"][0] == operation["saleID"][0], _["parsed_date"].date().day == (date_today.date().day - 1),\
                        _["parsed_date"].date().day > (date_today.date().day - 2)])]))),
                        "total_sum_operations_with_this_nmId_yesterday": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations \
                        if all([operation["nmId"] == _["nmId"], _["saleID"][0] == operation["saleID"][0], _["parsed_date"].date().day == (date_today.date().day - 1),\
                        _["parsed_date"].date().day > (date_today.date().day - 2)])]))),
                        "spp_percent": operation["spp"],
                        "spp_sum": digit_separator(math.ceil((operation["spp"]*operation["priceWithDisc"])/100)),
                        "img": img_link,
                        "finishedPrice": digit_separator(math.ceil(operation["finishedPrice"])),
                        "nmId": operation["nmId"],
                        "techSize": operation["techSize"],
                        "subject": operation["subject"],
                        "brand": operation["brand"],
                        "supplierArticle": operation["supplierArticle"],
                        "typeOperation": "Продажа 💰" if operation["saleID"][0] == "S" else "Возврат ↩️",
                        "feedbacks": feedbacks,
                        "reviewRating": reviewRating,
                        "warehouseName": operation["warehouseName"] + " → " + operation["regionName"],
                        "stocks_on_warehouses": stocks_on_warehouses,
                        "total_stocks_on_warehouses": total_stocks_on_warehouses,
                        "inWayToClient": digit_separator(in_way_to_client),
                        "inWayFromClient": digit_separator(in_way_from_client)
                    }    
                    if data_for_msg["typeOperation"] == "Продажа 💰":
                        status_send_msg_sell_in_tg = await sender_messeges_to_telegram(data_for_msg, subscription, type_operation = '2')
                        status_send_msg_ref_in_tg = False
                    else:
                        status_send_msg_ref_in_tg = await sender_messeges_to_telegram(data_for_msg, subscription, type_operation = '3')
                        status_send_msg_sell_in_tg = False
        if status_send_msg_sell_in_tg: 
            for id_wb_key in subscription['users']['2']['ids_wb_key']:           
                await update_time_last_in_wb(2, id_wb_key, time_last_sale_in_wb.isoformat())
        if status_send_msg_ref_in_tg:
            for id_wb_key in subscription['users']['3']['ids_wb_key']:   
                await update_time_last_in_wb(3, id_wb_key, time_last_refund_in_wb.isoformat())
    except Exception:
        import traceback
        logger.error(traceback.format_exc())