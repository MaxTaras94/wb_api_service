import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import OrmBase
from .user_model import User

class WB(OrmBase):
    __tablename__ = "wb_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_telegram_id: Mapped[BigInteger] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    api_key: Mapped[Optional[str]] = mapped_column(String())
    name_key: Mapped[String] = mapped_column(String())
   