from pydantic import BaseModel


# TODO: test
def to_camel_case(snake_str: str) -> str:
    pascal_case = "".join(x.capitalize() for x in snake_str.lower().split("_"))
    return snake_str[0].lower() + pascal_case[1:]


class CamelModel(BaseModel):
    class Config:
        alias_generator = to_camel_case
        allow_population_by_field_name = True
