from typing import Optional

from sqlalchemy import String, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import OrmBase


class TypeOperations(OrmBase):
    __tablename__ = "type_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    type_operation: Mapped[str] = mapped_column(Text())
    