import aiohttp
from app.logger import logger
from app.settings import settings
import requests
import urllib.parse


'''
Модуль для взаимодействия с ботом TG напрямую через HTTPS протокол
'''



async def send_message_to_tg(tg_user_id: int,
                             text_message: str,
                             link_img: str
                             ) -> dict:
    encoded_text_message = urllib.parse.quote(text_message)
    if link_img != "":
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto?chat_id={str(tg_user_id)}&photo={link_img}&caption={encoded_text_message}&parse_mode=HTML"
    else:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage?chat_id={str(tg_user_id)}&text={encoded_text_message}&parse_mode=HTML"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
        return {'status': data['ok'], 'tg_user_id': tg_user_id}
    except Exception as e:
        logger.error(e)
        return {'status': data['ok'], 'error': e, 'tg_user_id': tg_user_id}
        
async def check_user_is_subscriber_channel(tg_user_id: int) -> bool:
    '''Функция возвращает True, если пользователь подписан на канал. Иначе возвращает False
    '''
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getChatMember?chat_id=@xoxlov_maxim&user_id={str(tg_user_id)}"
    async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
    if data['ok'] == False or data['result']['status'] == 'left':
        return False
    else:
        return True