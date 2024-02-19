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
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto?chat_id={str(tg_user_id)}&photo={link_img}&caption={text_message}&parse_mode=HTML"
    async with aiohttp.ClientSession() as client:
        await client.get(url)
        
async def check_user_is_subscriber_channel(tg_user_id: int) -> bool:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getChatMember?chat_id=@testchannel1234567890134&user_id={str(tg_user_id)}"
    async with aiohttp.ClientSession() as client:
        res = await client.get(url)
    return res['ok']