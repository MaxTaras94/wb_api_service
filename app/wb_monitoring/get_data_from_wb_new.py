import asyncio
from app.logger import logger
from api.data_for_monitoring import OperationRegroupedDataResponse
from api.notifications import update_time_last_in_wb, get_time_last_in_wb
from app.digit_separator import digit_separator
from app.settings import settings
from app.send_requests_to_tg import send_message_with_photo
from app.templates.templates import render_template
import datetime
import httpx
import math
from random import random, randint
from typing import List, Tuple
import urllib.request
from urllib.parse import quote




def get_all_barcodes(operations: List[dict]) -> List[str]:
    '''Функция возвращает список уникальных bar-кодов по полученному списку заказов/продаж/возвратов
    '''
    return list(set([_["barcode"] for _ in operations]))


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

async def get_all_warehouses(api_key: str) -> List[dict]:
    '''Функция возвращает список всех пользовательских складов
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        warehouses = await client.get(settings.warehouses, headers=headers)
    return warehouses.json()

async def get_data_from_wb(link_operation_wb: str,
                           api_key: str,
                           date_and_time: str
                           ) -> List[dict]:
    '''Функция возвращает данные о заказах/продажах/возвратах из API WB 
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    date_and_time_yestarday = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    api_url_yestarday = link_operation_wb+"?dateFrom="+date_and_time_yestarday
    async with httpx.AsyncClient(timeout=30) as client:
       wb_data = await client.get(api_url_yestarday, headers=headers)
    response_data_yestarday = wb_data.json()
    logger.info(f"В ф-ции get_data_from_wb\n response_data_yestarday = {response_data_yestarday}")
    await asyncio.sleep(randint(1,5))
    return response_data_yestarday

async def get_stocks_from_wb(link_operation_wb: str,
                             api_key: str,
                             date_and_time: str
                             ) -> List[dict]:
    '''Функция возвращает данные об остатках из API WB 
    '''
    headers = {"Authorization": api_key, "content-Type": "application/json"}
    date_and_time_yestarday = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    api_url_stocks = settings.stockurl+"?dateFrom="+date_and_time
    async with httpx.AsyncClient(timeout=30) as client:
        stocks = await client.get(api_url_stocks, headers=headers)
    response_stock = stocks.json()
    logger.info(f"В ф-ции get_stocks_from_wb\n response_stock = {response_stock}")
    return response_stock

async def sender_messeges_to_tg(data_for_msg: dict,
                                subscription: OperationRegroupedDataResponse,
                                type_operation: str = None
                                ) -> None:   
    name_template = 'msg_with_orders_for_client.j2' if type_operation == "1" else "msg_with_sales_and_refunds_for_client.j2"
    telegram_ids = list(subscription['users'][type_operation]['telegram_ids'].keys())
    for num, tg_user_id in enumerate(telegram_ids):
        is_subscriber = subscription['users'][type_operation]['telegram_ids'][tg_user_id]['is_subscriber']
        if is_subscriber or is_subscriber is None:
            name_key = subscription['users'][type_operation]['names_wb_key'][num]
            data_for_msg['name_key'] = name_key if name_key is not None else subscription['api_key'][:10]+"..."+subscription['api_key'][-10:]
            text_msg = render_template(name_template, data={'data':data_for_msg, 'quote':quote})
            await send_message_with_photo(tg_user_id, text_msg, data_for_msg['img'])
        else:
            pass #TODO реализовать отправку сообщения, что т.к. отписан от канала - оповещения не может получать
    await asyncio.sleep(0.1)

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
    async with httpx.AsyncClient(timeout=30) as client:
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
    async with httpx.AsyncClient(timeout=30) as client:
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
    try:
        logger.info(f"В ф-ции parsing_order_data\n subscription = {subscription} \n orders = {orders}")
        for order in orders:
            date_and_time_order = order['parsed_date']
            if not order["isCancel"]:  
                if date_and_time_order > time_last_order_in_wb_from_db and date_and_time_order.date() >= date_today.date():
                    time_last_order_in_wb = date_and_time_order
                    feedbacks, reviewRating = await get_feedback_and_rating(order["nmId"])
                    img_link = await generic_link_for_nmId_img(order["nmId"])
                    data_for_msg = {
                        "date_and_time_order": date_and_time_order.strftime("%d.%m.%Y %H:%M:%S"),
                        "number_orders_with_this_nmId_today": digit_separator(math.ceil(sum([1 for _ in orders if _["nmId"] == order["nmId"] and \
                        _["parsed_date"] >= date_today and _["parsed_date"] <= date_and_time_order]))),
                        "number_orders_with_this_nmId_yesterday": digit_separator(math.ceil(sum([1 for _ in orders if _["nmId"] == order["nmId"] and \
                        _["parsed_date"] <= date_today]))),
                        "total_count_orders_today": digit_separator(math.ceil(sum([1 for _ in orders if _["parsed_date"] >= date_today and \
                        _["parsed_date"] <= date_and_time_order]))),
                        "total_sum_orders_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        _["parsed_date"] >= date_today and _["parsed_date"] <= date_and_time_order]))),
                        "total_sum_orders_with_this_nmId_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        _["nmId"] == order["nmId"] and _["parsed_date"] >= date_today and _["parsed_date"] <= date_and_time_order]))),
                        "total_sum_orders_with_this_nmId_yesterday": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in orders if \
                        _["nmId"] == order["nmId"] and _["parsed_date"] <= date_today]))),
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
                        "warehouseName": f"{order['warehouseName']} → {order['regionName']}"
                    }    
                    try:
                        data_for_msg['inWayToClient'] = digit_separator(sum([_['inWayToClient'] for _ in stocks if _["nmId"] == order["nmId"]]))
                        data_for_msg['inWayFromClient'] = digit_separator((sum([_['inWayFromClient'] for _ in stocks if _["nmId"] == order["nmId"]])))
                        data_for_msg['quantity'] = digit_separator(sum([_['quantity'] for _ in stocks if _["nmId"] == order["nmId"]]))
                    except TypeError:
                        data_for_msg['inWayToClient'] = "?"
                        data_for_msg['inWayFromClient'] = "?"
                        data_for_msg['quantity'] = "?"
                    await sender_messeges_to_tg(data_for_msg, subscription, type_operation = '1')
        for id_wb_key in subscription['users']['1']['ids_wb_key']:           
            await update_time_last_in_wb(1, id_wb_key, time_last_order_in_wb.isoformat())
    except Exception as e:
        logger.error(f"Текст ошибки: {e}")


async def parsing_sales_refunds_data(operations_from_wb: List[List[dict]],
                                     subscription: OperationRegroupedDataResponse
                                     ) -> None:
    '''Функция на вход получает ответ от API WB о продажах или возвратах.
       Возвращает распаршенный ответ в виде List[List[dict]]
    '''
    date_today_str = datetime.datetime.today().strftime("%Y-%m-%d")
    date_today = datetime.datetime.strptime(date_today_str, "%Y-%m-%d")
    time_last_sale_in_wb_from_db = await get_last_time_operation(2, subscription['users']['2']['ids_wb_key'][0], date_today)
    time_last_refund_in_wb_from_db = await get_last_time_operation(3, subscription['users']['3']['ids_wb_key'][0], date_today)
    stocks = operations_from_wb[1]
    operations = operations_sorter(operations_from_wb[0])
    time_last_sale_in_wb = time_last_sale_in_wb_from_db
    time_last_refund_in_wb = time_last_refund_in_wb_from_db
    try:
        logger.info(f"В ф-ции parsing_sales_refunds_data \n subscription = {subscription} \n operations = {operations}")
        for operation in operations:
            date_and_time_operation = operation["parsed_date"]
            if date_and_time_operation.date() >= date_today.date():
                if operation["saleID"][0] == "S" and date_and_time_operation > time_last_sale_in_wb_from_db or operation["saleID"][0] == "R" and \
                date_and_time_operation > time_last_refund_in_wb_from_db:
                    feedbacks, reviewRating = await get_feedback_and_rating(operation["nmId"])
                    img_link = await generic_link_for_nmId_img(operation["nmId"])
                    time_last_sale_in_wb = date_and_time_operation if operation["saleID"][0] == "S" else time_last_sale_in_wb_from_db
                    time_last_refund_in_wb = date_and_time_operation if operation["saleID"][0] == "R" else time_last_refund_in_wb_from_db
                    data_for_msg = {
                        "date_and_time_operation": date_and_time_operation.strftime("%d.%m.%Y %H:%M:%S"),
                        "number_operations_with_this_nmId_today": digit_separator(math.ceil(sum([1 for _ in operations if _["nmId"] == operation["nmId"] \
                        and all([_["saleID"][0] == operation["saleID"][0], _["parsed_date"] <= date_and_time_operation,\
                        _["parsed_date"] >= date_today])]))),
                        "total_sum_operations_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations if all([_["saleID"][0] == operation["saleID"][0],\
                        _["parsed_date"] <= date_and_time_operation, _["parsed_date"] >= date_today])]))),
                        "total_sum_operations_with_this_nmId_today": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations \
                        if all([_["nmId"] == operation["nmId"], _["saleID"][0] == operation["saleID"][0], \
                        _["parsed_date"] <= date_and_time_operation, _["parsed_date"] >= date_today])]))),
                        "total_count_operations_today": digit_separator(math.ceil(sum([1 for _ in operations if all([_["saleID"][0] == operation["saleID"][0],\
                        _["parsed_date"] <= date_and_time_operation, _["parsed_date"] >= date_today])]))),
                        "number_operations_with_this_nmId_yesterday": digit_separator(math.ceil(sum([1 for _ in operations if _["nmId"] == operation["nmId"] \
                        and _["saleID"][0] == operation["saleID"][0]]))),
                        "total_sum_operations_with_this_nmId_yesterday": digit_separator(math.ceil(sum([_["finishedPrice"] for _ in operations \
                        if operation["nmId"] == _["nmId"] and _["saleID"][0] == operation["saleID"][0]]))),
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
                        "warehouseName": operation["warehouseName"] +" → "+operation["regionName"]
                    }    
                    try:
                        data_for_msg['inWayToClient'] = digit_separator(sum([_['inWayToClient'] for _ in stocks if _["nmId"] == operation["nmId"]]))
                        data_for_msg['inWayFromClient'] = digit_separator(sum([_['inWayFromClient'] for _ in stocks if _["nmId"] == operation["nmId"]]))
                        data_for_msg['quantity'] = digit_separator(sum([_['quantity'] for _ in stocks if _["nmId"] == operation["nmId"]]))
                    except TypeError:
                        data_for_msg['inWayToClient'] = "?"
                        data_for_msg['inWayFromClient'] = "?"
                        data_for_msg['quantity'] = "?"
                    if data_for_msg["typeOperation"] == "Продажа 💰":
                        await sender_messeges_to_tg(data_for_msg, subscription, type_operation = '2')
                    else:
                        await sender_messeges_to_tg(data_for_msg, subscription, type_operation = '3')
        for id_wb_key in subscription['users']['2']['ids_wb_key']:           
            await update_time_last_in_wb(2, id_wb_key, time_last_sale_in_wb.isoformat())
        for id_wb_key in subscription['users']['3']['ids_wb_key']:   
            await update_time_last_in_wb(3, id_wb_key, time_last_refund_in_wb.isoformat())
    except Exception as e:
        logger.error(f"Текст ошибки: {e}")