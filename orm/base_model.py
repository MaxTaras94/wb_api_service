from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Соглашение об именовании по умолчанию для всех индексов и ограничений
# Узнайте, почему это важно и как это сэкономит ваше время:
# https://alembic.sqlalchemy.org/en/latest/naming.html
convention = {
    "all_column_names": lambda constraint, table: "_".join(
        [column.name for column in constraint.columns.values()]
    ),
    "ix": "ix__%(table_name)s__%(all_column_names)s",
    "uq": "uq__%(table_name)s__%(all_column_names)s",
    "ck": "ck__%(table_name)s__%(constraint_name)s",
    "fk": "fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s",
    "pk": "pk__%(table_name)s",
}


class OrmBase(DeclarativeBase):
    metadata = MetaData(naming_convention=convention) 
