"""Persisted configuration for the single local final-render pipeline."""
from sqlalchemy import JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RenderConfiguration(Base):
    __tablename__ = 'render_configuration'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
