
import datetime
import orm
from typing import Literal, Optional
from fastapi import APIRouter, Depends, status, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import uuid



class WBDataIDResponse(BaseModel):
    id: int
    name_key: Optional[str]
    api_key: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class WBDataIDTGResponse(BaseModel):
    user_telegram_id: int
    api_key: Optional[str]
    name_key: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)
    

class APIWBKeysListResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: list[WBDataIDResponse]


router = APIRouter()

    

@router.get("/get_wb_keys/{user_telegram_id}/", response_model=APIWBKeysListResponse)
async def get_wb_keys(user_telegram_id: int, 
                      session: AsyncSession = Depends(orm.get_session)
                      ) -> JSONResponse:
    statement = select(orm.WB.id, orm.WB.name_key, orm.WB.api_key).where(orm.WB.user_telegram_id == user_telegram_id)
    wb_keys_results = await session.execute(statement)
    response_data = [
        WBDataIDResponse.model_validate(u).model_dump() for u in wb_keys_results.all()
    ]
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_data
        }
    )
    
@router.delete("/delete_wb_key/{wb_key_id}", response_model=WBDataIDResponse, status_code=status.HTTP_200_OK)
async def delete_wb_key_for_user(wb_key_id: int,
                                 session: AsyncSession = Depends(orm.get_session)
                                ) -> JSONResponse:
    try:
        statement = delete(orm.WB).where(orm.WB.id == wb_key_id)
        wb_keys_results = await session.execute(statement)
        await session.commit()
        return JSONResponse(
            content={
                "status": "ok",
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "text_error": e
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.post("/set_wb_key", response_model=WBDataIDTGResponse, status_code=status.HTTP_201_CREATED)
async def set_wb_key_for_user(wb_data: WBDataIDTGResponse,
                              session: AsyncSession = Depends(orm.get_session),
                              ) -> JSONResponse:
    wb_data_dump = wb_data.model_dump()
    wb_candidate = orm.WB(**wb_data_dump)
    try:
        session.add(wb_candidate)
        await session.commit()
        await session.refresh(wb_candidate)
        response_model = WBDataIDTGResponse.model_validate(wb_candidate)
    except Exception as e:
        return JSONResponse(
                content={
                    "status": "error",
                    "data": {"text_error": e},
                        },
                status_code=status.HTTP_400_BAD_REQUEST,
                )
    return JSONResponse(
        content={
            "status": "ok",
            "data": response_model.model_dump(),
                },
        status_code=status.HTTP_201_CREATED,
        )