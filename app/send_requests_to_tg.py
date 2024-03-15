from app.settings import settings
import aiohttp



'''
Модуль для взаимодействия с ботом TG напрямую через HTTPS протокол
'''



async def send_message_with_photo(
                                   tg_user_id: int,
                                   text_message: str,
                                   link_img: str
                                  ) -> None:
    if link_img != "":
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto?chat_id={str(tg_user_id)}&photo={link_img}&caption={text_message}&parse_mode=HTML"
    else:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage?chat_id={str(tg_user_id)}&text={text_message}&parse_mode=HTML"
    async with aiohttp.ClientSession() as client:
        try:
            await client.get(url)
        except:
            pass
        
async def check_user_is_subscriber_channel(tg_user_id: int) -> bool:
    '''Функция возвращает True, если пользователь подписан на канал. Иначе возвращает False
    '''
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getChatMember?chat_id=@xoxlov_maxim&user_id={str(tg_user_id)}"
    async with aiohttp.ClientSession() as client:
        async with client.get(url) as subscribe:
            data = await subscribe.json()
    if data['ok'] == False or data['result']['status'] == 'left':
        return False
    else:
        return True