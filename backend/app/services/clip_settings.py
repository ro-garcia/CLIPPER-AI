from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base, Session
from ..config import settings


class ClipTimingRow(Base):
    __tablename__ = 'clip_timing'
    id: Mapped[int] = mapped_column(primary_key=True)
    before_seconds: Mapped[int] = mapped_column(default=30)
    after_seconds: Mapped[int] = mapped_column(default=15)


class ClipTiming(BaseModel):
    before_seconds: int = Field(30, ge=1, le=300, strict=True)
    after_seconds: int = Field(15, ge=0, le=300, strict=True)

    @model_validator(mode='after')
    def limits(self):
        if self.before_seconds + self.after_seconds > 300:
            raise ValueError('La duración total no puede superar 300 segundos.')
        if self.before_seconds > settings.buffer_minutes * 60:
            raise ValueError('El tiempo anterior no puede superar la capacidad del buffer.')
        return self


def get_timing():
    with Session() as db:
        row = db.get(ClipTimingRow, 1)
        return {'before_seconds': min(row.before_seconds if row else 30, settings.buffer_minutes * 60),
                'after_seconds': row.after_seconds if row else 15}


def save_timing(value: ClipTiming):
    with Session.begin() as db:
        row = db.get(ClipTimingRow, 1)
        if row is None:
            row = ClipTimingRow(id=1)
            db.add(row)
        row.before_seconds = value.before_seconds
        row.after_seconds = value.after_seconds
    return value.model_dump()
