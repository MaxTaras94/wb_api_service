import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import OrmBase
from .user_model import User

class CheckSubscribe(OrmBase):
    __tablename__ = "check_subscribe"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    is_subscriber: Mapped[bool] = mapped_column(Boolean())
    