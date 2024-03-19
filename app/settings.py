from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WB Service API"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    db_host: str
    db_name: str
    db_port: int
    db_user: str
    db_pass: str
    ordersurl: str
    salesurl: str
    stockurl: str
    warehouses: str
    warehouses_stocks: str
    telegram_bot_token: str
    sendmsgtg: str
    debug: bool
    templates_dir: str
    server_host: str
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def tg_sendmsg_url(self, user_id: int, text_message: str) -> str:
        return f"{self.sendmsgtg}/bot{self.telegram_bot_token}/sendMessage?chat_id={user_id}&text={text_message}"
    
    project_root: Path = Path(__file__).parent.parent.resolve()

    
    class Config:
        env_file = '.env'

settings = Settings()