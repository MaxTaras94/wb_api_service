import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import OrmBase


class BotSettings(OrmBase):
    __tablename__ = "botsettings"

    id: Mapped[int] = mapped_column(primary_key=True)
    on_off: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    setting_name: Mapped[str] = mapped_column(String(255), nullable=False)
    setting_description: Mapped[str] = mapped_column(Text)
    