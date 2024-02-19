import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import OrmBase
from .user_model import User
from .type_operation_model import TypeOperations


class Notification(OrmBase):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    wb_api_keys_id: Mapped[Integer] = mapped_column(Integer, ForeignKey("wb_api_keys.id"))
    type_operation_id: Mapped[Integer] = mapped_column(Integer, ForeignKey("type_operations.id"))
    is_checking: Mapped[Boolean] = mapped_column(Boolean())
    time_last_in_wb: Mapped[datetime.datetime] = mapped_column(DateTime())
    
    type_operation = relationship("TypeOperations")