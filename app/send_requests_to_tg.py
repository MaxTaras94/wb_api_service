import aiohttp
from app.settings import settings
import httpx



'''
Модуль для взаимодействия с ботом TG напрямую через HTTPS протокол
'''



async def send_message_to_tg(tg_user_id: int,
                             text_message: str,
                             link_img: str
                             ) -> dict:
    if link_img != "":
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto?chat_id={str(tg_user_id)}&photo={link_img}&caption={text_message}&parse_mode=HTML"
    else:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage?chat_id={str(tg_user_id)}&text={text_message}&parse_mode=HTML"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return {'status': data['ok'], 'description': data['description'], 'tg_user_id': tg_user_id}
    except Exception as e:
        return {'status': data['ok'], 'description': data['description'], 'error': e, 'tg_user_id': tg_user_id}
        
async def check_user_is_subscriber_channel(tg_user_id: int) -> bool:
    '''Функция возвращает True, если пользователь подписан на канал. Иначе возвращает False
    '''
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getChatMember?chat_id=@xoxlov_maxim&user_id={str(tg_user_id)}"
    async with httpx.AsyncClient(timeout=30) as client:
        subscribe = await client.get(url)
    data = subscribe.json()
    if data['ok'] == False or data['result']['status'] == 'left':
        return False
    else:
        return True