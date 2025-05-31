from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class TemplateBase(BaseModel):
    name: str
    content: str

class TemplateCreate(TemplateBase):
    pass

class Template(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NewsletterBase(BaseModel):
    title: str
    content: str
    status: str  # draft, scheduled, sent
    scheduled_date: Optional[datetime] = None
    template_id: Optional[int] = None
    image_url: Optional[str] = None

class NewsletterCreate(NewsletterBase):
    pass

class NewsletterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    template_id: Optional[int] = None
    image_url: Optional[str] = None

class Newsletter(NewsletterBase):
    id: int
    created_at: datetime
    updated_at: datetime
    template: Optional[Template] = None

class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(UserBase):
    id: int

    class Config:
        from_attributes = True

class User(UserBase):
    id: int

    class Config:
        from_attributes = True 