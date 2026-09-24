from datetime import datetime, timezone
from sqlalchemy import JSON, create_engine, String, Float, Integer, Text, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

class Stream(Base):
    __tablename__ = 'streams'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=lambda: datetime.now(timezone.utc).isoformat())

class Transcript(Base):
    __tablename__ = 'transcriptions'
    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[str] = mapped_column(index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

class Clip(Base):
    __tablename__ = 'clips'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(default='capturing')
    duration: Mapped[float] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(default='')
    # Source times make Phase 4 subtitles reuse the timestamps already produced by Whisper.
    source_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    render_status: Mapped[str] = mapped_column(String, default='NOT_RENDERED', index=True)
    render_progress: Mapped[int] = mapped_column(Integer, default=0)
    render_stage: Mapped[str] = mapped_column(String, default='')
    render_error: Mapped[str] = mapped_column(Text, default='')
    render_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rendered_at: Mapped[str] = mapped_column(String, default='')
    metadata_status: Mapped[str] = mapped_column(String, default='METADATA_PENDING', index=True)
    metadata_error: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(default=lambda: datetime.now(timezone.utc).isoformat())

engine = create_engine(f'sqlite:///{settings.storage_dir / "liveclip.db"}', connect_args={'check_same_thread': False})
@event.listens_for(engine, 'connect')
def configure_sqlite(connection, _):
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA busy_timeout=5000')

Session = sessionmaker(engine, expire_on_commit=False)

def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


_CLIP_RENDER_COLUMNS = {
    'source_start': 'REAL', 'source_end': 'REAL',
    "render_status": "TEXT NOT NULL DEFAULT 'NOT_RENDERED'",
    'render_progress': 'INTEGER NOT NULL DEFAULT 0', 'render_stage': "TEXT NOT NULL DEFAULT ''",
    'render_error': "TEXT NOT NULL DEFAULT ''", 'render_settings': 'JSON',
    'output_width': 'INTEGER', 'output_height': 'INTEGER', 'rendered_at': "TEXT NOT NULL DEFAULT ''",
    'metadata_status': "TEXT NOT NULL DEFAULT 'METADATA_PENDING'",
    'metadata_error': "TEXT NOT NULL DEFAULT ''",
}


def upgrade_clip_schema() -> None:
    """Add Phase 4/5 metadata without touching existing clips or their files."""
    with engine.begin() as connection:
        exists = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='clips'"))
        if exists.scalar() is None:
            return
        names = {row[1] for row in connection.execute(text('PRAGMA table_info(clips)'))}
        for name, definition in _CLIP_RENDER_COLUMNS.items():
            if name not in names:
                connection.execute(text(f'ALTER TABLE clips ADD COLUMN {name} {definition}'))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_clips_render_status ON clips (render_status)'))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_clips_metadata_status ON clips (metadata_status)'))
