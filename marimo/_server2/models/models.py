from __future__ import annotations

from typing import Any, Union

from marimo._server2.models.base import CamelModel

UIElementId = str


class UpdateComponentValuesRequest(CamelModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class InstantiateRequest(CamelModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class FunctionCallRequest(CamelModel):
    function_call_id: str
    namespace: str
    function_name: str
    args: dict[str, Any]


class BaseResponse(CamelModel):
    success: bool


class SuccessResponse(BaseResponse):
    success: bool = True
