# Copyright 2024 Marimo. All rights reserved.
import pydantic


def to_camel_case(snake_str: str) -> str:
    if snake_str == "":
        return ""

    if "_" not in snake_str:
        return snake_str

    pascal_case = "".join(x.capitalize() for x in snake_str.lower().split("_"))
    return snake_str[0].lower() + pascal_case[1:]


class CamelModel(pydantic.BaseModel):
    class Config:
        alias_generator = to_camel_case
        if pydantic.__version__[0] == "1":
            allow_population_by_field_name = True
        else:
            populate_by_name = True
