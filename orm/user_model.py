from typing import Optional

from sqlalchemy import String, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import OrmBase


class User(OrmBase):
    __tablename__ = "users"

    telegram_id: Mapped[BigInteger] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(Text())
    source: Mapped[Optional[str]] = mapped_column(Text())
