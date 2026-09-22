from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Boolean, UniqueConstraint, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

class Base(DeclarativeBase): pass
class Source(Base):
    __tablename__="source_registry"; __table_args__=(UniqueConstraint("provider", "board_token", name="uq_source_provider_token"),)
    id: Mapped[int]=mapped_column(primary_key=True); provider: Mapped[str]=mapped_column(String(32), index=True); company_name: Mapped[str]=mapped_column(String(255))
    board_token: Mapped[str]=mapped_column(String(512)); base_url: Mapped[str]=mapped_column(Text); careers_url: Mapped[str|None]=mapped_column(Text, nullable=True)
    status: Mapped[str]=mapped_column(String(16), default="WATCHLIST"); verification_status: Mapped[str]=mapped_column(String(16), default="UNVERIFIED")
    source_origin: Mapped[str]=mapped_column(String(255), default="seed"); consecutive_failures: Mapped[int]=mapped_column(Integer, default=0); open_job_count: Mapped[int]=mapped_column(Integer, default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Job(Base):
    __tablename__="jobs"; __table_args__=(UniqueConstraint("canonical_job_key", name="uq_job_key"),)
    id: Mapped[int]=mapped_column(primary_key=True); source_id: Mapped[int|None]=mapped_column(Integer, index=True, nullable=True); canonical_job_key: Mapped[str]=mapped_column(String(128), index=True); provider: Mapped[str]=mapped_column(String(32)); external_job_id: Mapped[str]=mapped_column(String(255))
    company_name: Mapped[str]=mapped_column(String(255)); title: Mapped[str]=mapped_column(String(512)); canonical_url: Mapped[str]=mapped_column(Text); apply_url: Mapped[str]=mapped_column(Text)
    description_text: Mapped[str]=mapped_column(Text, default=""); content_hash: Mapped[str]=mapped_column(String(64)); locations: Mapped[str]=mapped_column(Text, default="[]")
    live_status: Mapped[str]=mapped_column(String(16), default="UNCERTAIN"); notified: Mapped[bool]=mapped_column(Boolean, default=False, index=True); first_seen_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)); last_seen_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)); last_changed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
class Resume(Base):
    __tablename__="resumes"; __table_args__=(UniqueConstraint("file_sha256", name="uq_resume_hash"),)
    id: Mapped[int]=mapped_column(primary_key=True); resume_id: Mapped[str]=mapped_column(String(64), unique=True); category: Mapped[str]=mapped_column(String(64)); source_file: Mapped[str]=mapped_column(Text); file_sha256: Mapped[str]=mapped_column(String(64)); payload: Mapped[str]=mapped_column(Text)
class Notification(Base):
    __tablename__="notifications"; __table_args__=(UniqueConstraint("job_id", name="uq_notification_job"),)
    id: Mapped[int]=mapped_column(primary_key=True); job_id: Mapped[int]=mapped_column(index=True); status: Mapped[str]=mapped_column(String(16), default="PENDING"); sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

def engine(url: str): return create_async_engine(url, future=True)
async def migrate(url: str):
    e=engine(url)
    async with e.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        # Additive migration keeps existing local databases usable; production migrations are repeatable.
        for statement in ["ALTER TABLE jobs ADD COLUMN source_id INTEGER", "ALTER TABLE jobs ADD COLUMN last_seen_at DATETIME", "ALTER TABLE jobs ADD COLUMN last_changed_at DATETIME"]:
            try: await c.execute(text(statement))
            except Exception: pass
    await e.dispose()
def sessions(url: str): return async_sessionmaker(engine(url), expire_on_commit=False)
