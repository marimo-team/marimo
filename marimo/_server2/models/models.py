from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel

UIElementId = str


class UpdateComponentValuesRequest(BaseModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class InstantiateRequest(BaseModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class FunctionCallRequest(BaseModel):
    function_call_id: str
    namespace: str
    function_name: str
    args: dict[str, Any]


class BaseResponse(BaseModel):
    success: bool


class SuccessResponse(BaseResponse):
    success: bool = True
