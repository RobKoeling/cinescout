"""WatchlistItem model — a film on a user's (Letterboxd-imported) watchlist."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.film import Film
    from cinescout.models.user import User


class WatchlistItem(Base, TimestampMixin):
    """A film the user intends to watch. Synced wholesale from Letterboxd's watchlist."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "film_id", name="uq_user_watchlist_film"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    film_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="watchlist_items")
    film: Mapped["Film"] = relationship()

    def __repr__(self) -> str:
        return f"<WatchlistItem(user_id={self.user_id!r}, film_id={self.film_id!r})>"
