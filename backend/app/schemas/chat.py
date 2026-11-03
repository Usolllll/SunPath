from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=12000)

    @field_validator('content')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('消息不能为空')
        return value.strip()


class ChatIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    messages: list[ChatMessage] = Field(min_length=1, max_length=21)
    use_profile: bool = True
    use_saved_plans: bool = True
    plan_ids: list[StrictInt] | None = Field(default=None, max_length=10)

    @field_validator('plan_ids')
    @classmethod
    def unique_plan_ids(cls, value):
        if value is not None and (len(value) != len(set(value)) or any(plan_id < 1 for plan_id in value)):
            raise ValueError('方案 ID 必须是不同的正整数')
        return value

    @model_validator(mode='after')
    def validate_conversation(self):
        if any(message.role != ('user' if index % 2 == 0 else 'assistant') for index, message in enumerate(self.messages)) or self.messages[-1].role != 'user':
            raise ValueError('对话须从用户问题开始，问答交替，并以用户问题结束')
        if len(self.messages[-1].content) > 1000:
            raise ValueError('每次提问最多 1000 字')
        if sum(len(message.content) for message in self.messages) > 32000:
            raise ValueError('当前对话过长，请开启新对话')
        return self


class ChatContextSummary(BaseModel):
    profile_included: bool
    saved_plans_enabled: bool
    total_saved_plans: int
    requested_plan_count: int
    included_plan_count: int
    omitted_plan_count: int
    plan_names: list[str]
    max_plans: int


class ChatOut(BaseModel):
    content: str
    model: str
    model_label: str
    finish_reason: str
    context: ChatContextSummary | None = None
