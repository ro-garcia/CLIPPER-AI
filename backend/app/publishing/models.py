from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..detection.models import now


class SocialAccount(Base):
    __tablename__ = 'social_accounts'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    platform: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String)
    external_account_id: Mapped[str] = mapped_column(String, default='')
    status: Mapped[str] = mapped_column(String, default='DISCONNECTED', index=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    token_reference: Mapped[str] = mapped_column(String, default='')
    expires_at: Mapped[str] = mapped_column(String, default='')
    last_validation: Mapped[str] = mapped_column(String, default='')
    provider_mode: Mapped[str] = mapped_column(String, default='real')
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class PublicationJob(Base):
    __tablename__ = 'publication_jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    clip_id: Mapped[str] = mapped_column(ForeignKey('clips.id'), index=True)
    platform: Mapped[str] = mapped_column(String, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('social_accounts.id'), index=True)
    status: Mapped[str] = mapped_column(String, default='DRAFT', index=True)
    scheduled_at: Mapped[str] = mapped_column(String, default='', index=True)
    started_at: Mapped[str] = mapped_column(String, default='')
    published_at: Mapped[str] = mapped_column(String, default='')
    platform_media_id: Mapped[str] = mapped_column(String, default='')
    publication_url: Mapped[str] = mapped_column(Text, default='')
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(String, default='')
    last_error: Mapped[str] = mapped_column(Text, default='')
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String, default='')
    explicit_republish: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class PublicationAttempt(Base):
    __tablename__ = 'publication_attempts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('publication_jobs.id'), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    error_code: Mapped[str] = mapped_column(String, default='')
    error_message: Mapped[str] = mapped_column(Text, default='')
    started_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str] = mapped_column(default='')


class PublishingConfiguration(Base):
    __tablename__ = 'publishing_configuration'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class OAuthSession(Base):
    __tablename__ = 'publishing_oauth_sessions'
    state: Mapped[str] = mapped_column(String, primary_key=True)
    platform: Mapped[str] = mapped_column(String)
    code_verifier: Mapped[str] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)
