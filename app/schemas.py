from pydantic import BaseModel, Field
from typing import Optional

class LoginBody(BaseModel):
    username: str
    password: str

class MePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=4)
