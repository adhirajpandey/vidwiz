from datetime import datetime
from pydantic import BaseModel, ConfigDict


def datetime_to_gmt_str(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


class ApiModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: datetime_to_gmt_str},
    )


class ErrorDetail(ApiModel):
    field: str | None = None
    message: str
    type: str | None = None


class ErrorPayload(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail] | dict[str, object] | None = None


class ErrorResponse(ApiModel):
    error: ErrorPayload
