from pydantic import BaseModel, ConfigDict, Field, StrictInt


class AIMatchIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    count: int = Field(default=12, ge=3, le=30, strict=True)


class AISelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    group_ids: list[StrictInt] = Field(min_length=1, max_length=30)
