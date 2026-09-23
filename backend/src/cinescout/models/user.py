"""User model for authentication and profile data."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.watch_log import WatchLog
    from cinescout.models.watchlist_item import WatchlistItem


class User(Base, TimestampMixin):
    """Registered CineScout user (username/password auth)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Letterboxd integration (phase 1: read-only link, 1:1 with User).
    letterboxd_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    letterboxd_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    watch_logs: Mapped[list["WatchLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, username={self.username!r})>"
