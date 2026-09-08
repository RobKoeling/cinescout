"""WatchLog model — a user's record of having watched a film."""

from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.film import Film
    from cinescout.models.showing import Showing
    from cinescout.models.user import User


class WatchLog(Base, TimestampMixin):
    """
    A user's log entry for having watched a film.

    Either tied to a tracked Showing (showing_id set, film/date auto-filled
    from the showing) or a manual entry (showing_id NULL, watched_date
    user-supplied).

    The uq_user_showing constraint only prevents double-logging the *same*
    showing — Postgres treats NULL as distinct in unique indexes, so it does
    not limit how many manual entries (showing_id IS NULL) a user can have.
    Do not "fix" this into a partial index; it's intentional.
    """

    __tablename__ = "watch_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "showing_id", name="uq_user_showing"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0.5 AND rating <= 5.0)",
            name="ck_watch_log_rating_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Always set, even for showing-linked entries — denormalized so the
    # diary can be queried without joining through Showing.
    film_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL for manual entries. SET NULL (not CASCADE) on delete: if a Showing
    # is ever purged, demote this entry to manual-style rather than silently
    # destroying the user's rating/comment/history for a film they watched.
    showing_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("showings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # For showing-linked entries, derived server-side from Showing.start_time
    # (Europe/London date) at creation time — never trust client input there.
    watched_date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)

    # 0.5-5.0 in 0.5 increments, matching Letterboxd's scale.
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="watch_logs")
    film: Mapped["Film"] = relationship()
    showing: Mapped["Showing | None"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<WatchLog(user_id={self.user_id!r}, film_id={self.film_id!r}, "
            f"showing_id={self.showing_id!r}, watched_date={self.watched_date})>"
        )
