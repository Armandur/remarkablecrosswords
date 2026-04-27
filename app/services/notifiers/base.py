from typing import Protocol, TypedDict, Literal, Any, Optional

class FieldOption(TypedDict):
    value: str
    label: str

class FieldSpec(TypedDict):
    name: str
    label: str
    type: Literal["text", "password", "select"]
    placeholder: Optional[str]
    default: Optional[Any]
    help_text: Optional[str]
    options: Optional[list[FieldOption]]

class Notifier(Protocol):
    KIND: str
    LABEL: str
    CONFIG_FIELDS: list[FieldSpec]
    
    def __init__(self, config: dict):
        ...
        
    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        ...
