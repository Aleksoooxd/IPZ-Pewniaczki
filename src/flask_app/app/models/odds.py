from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from ..db import db


class MatchOdds(db.Model):
    """Bookmaker odds for an already-played (:class:`FootballMatch`) match.

    Stores the average (``Avg*``) and best (``Max*``) decimal odds across
    bookmakers for each outcome, sourced from football-data.co.uk. One row per
    match; used by the value/EV calculator and historical backtests.
    """

    __tablename__ = "match_odds"

    odds_id    = Column(Integer, primary_key=True)
    match_id   = Column(Integer, ForeignKey("football_match.match_id"),
                        unique=True, nullable=False)
    avg_home   = Column(Float, nullable=True)
    avg_draw   = Column(Float, nullable=True)
    avg_away   = Column(Float, nullable=True)
    best_home  = Column(Float, nullable=True)
    best_draw  = Column(Float, nullable=True)
    best_away  = Column(Float, nullable=True)
    source     = Column(String, nullable=True)

    match = relationship("FootballMatch", back_populates="match_odds")


class FutureMatchOdds(db.Model):
    """Bookmaker odds for an upcoming (:class:`FutureMatch`) fixture.

    Mirrors :class:`MatchOdds` for not-yet-played matches, with a ``fetched_at``
    timestamp so the live feed can be refreshed periodically.
    """

    __tablename__ = "future_match_odds"

    odds_id    = Column(Integer, primary_key=True)
    match_id   = Column(Integer, ForeignKey("future_match.match_id"),
                        unique=True, nullable=False)
    avg_home   = Column(Float, nullable=True)
    avg_draw   = Column(Float, nullable=True)
    avg_away   = Column(Float, nullable=True)
    best_home  = Column(Float, nullable=True)
    best_draw  = Column(Float, nullable=True)
    best_away  = Column(Float, nullable=True)
    fetched_at = Column(DateTime, nullable=True)

    future_match = relationship("FutureMatch", back_populates="future_odds")
