from pydantic import BaseModel, ConfigDict, Field, field_validator


class Parameter(BaseModel):
    name: str
    value: str


class Property(BaseModel):
    name: str
    group: str
    parameters: list[Parameter]
    values: list[str]


class CardDate(BaseModel):
    date: str
    time: str
    text: str
    is_text: bool
    utc: bool


class ParsedCard(BaseModel):
    formatted_name: str
    formatted_name_property: Property
    properties: list[Property]
    birthday: CardDate | None = None
    anniversary: CardDate | None = None
    vcard: str


class CardRecord(ParsedCard):
    id: str
    created_at: str
    updated_at: str


class CardInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    formatted_name: str = Field(min_length=1, max_length=512)

    @field_validator('formatted_name')
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('A nonempty name without control characters is required')
        return value


class ValidationResult(BaseModel):
    valid: bool = True


class Health(BaseModel):
    status: str = 'ok'
    native_parser: str = 'ready'
    persistence: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
