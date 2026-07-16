from sqlalchemy import Column, Integer, String, Date, Float, Boolean, ForeignKey, select
from sqlalchemy.orm import relationship

from ..db import db


class FootballMatch(db.Model):
    """A played football match and its derived attributes.

    Stores the fixture (league/season/date/teams), the final result and scores,
    the ELO ratings captured at match time, surprise flags, and the model
    consensus label. Related rows (stats, form, predictions) are reached via
    relationships.
    """
    __tablename__ = "football_match"

    match_id        = Column(Integer, primary_key=True)
    league_id       = Column(Integer, ForeignKey("league.league_id"))
    season_id       = Column(Integer, ForeignKey("season.season_id"))
    date            = Column(Date)
    home_team_id    = Column(Integer, ForeignKey("team.team_id"))
    away_team_id    = Column(Integer, ForeignKey("team.team_id"))
    result          = Column(String)
    home_matchday   = Column(Integer)
    away_matchday   = Column(Integer)
    round           = Column(Integer, nullable=True)  # canonical round = max(home, away) matchday
    home_elo        = Column(Float,   nullable=True)
    away_elo        = Column(Float,   nullable=True)
    home_elo_change = Column(Float,   nullable=True)
    away_elo_change = Column(Float,   nullable=True)
    fthg            = Column(Integer)
    ftag            = Column(Integer)
    is_surprise     = Column(Boolean)
    is_surprise_h    = Column(Boolean)
    is_surprise_d    = Column(Boolean)
    is_surprise_a    = Column(Boolean)
    consensus       = Column(String)

    league      = relationship("League",      back_populates="matches")
    season      = relationship("Season",      back_populates="matches")
    home_team   = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team   = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    match_stats = relationship("MatchStats",  back_populates="match")
    form_data   = relationship("MatchForm",   back_populates="match")
    predictions = relationship("Predicted",   back_populates="match")


class FutureMatch(db.Model):
    """A scheduled (not-yet-played) football match.

    Mirrors :class:`FootballMatch` for upcoming fixtures: league/season, date,
    kick-off time, and the two teams. Predictions are linked via
    ``future_predictions``.
    """
    __tablename__ = "future_match"

    match_id      = Column(Integer, primary_key=True)
    league_id     = Column(Integer, ForeignKey("league.league_id"))
    season_id     = Column(Integer, ForeignKey("season.season_id"))
    home_matchday = Column(Integer)
    round         = Column(Integer, nullable=True)
    date          = Column(Date)
    time          = Column(String(5))
    home_team_id  = Column(Integer, ForeignKey("team.team_id"))
    away_team_id  = Column(Integer, ForeignKey("team.team_id"))

    league             = relationship("League",  back_populates="future_match")
    season             = relationship("Season",  back_populates="future_match")
    home_team          = relationship("Team",    foreign_keys=[home_team_id])
    away_team          = relationship("Team",    foreign_keys=[away_team_id])
    future_predictions = relationship("PredictedFuture", back_populates="future_match")


class MatchStats(db.Model):
    """Per-team, per-match dispersion/diversity statistics.

    Holds six summary metrics (mean, std, shannon, cv, gini, hhi) describing
    the distribution of that team's season-long results up to a given match.
    One row exists per ``(match_id, team_side)``.
    """
    __tablename__ = "match_stats"

    stat_id   = Column(Integer, primary_key=True)
    match_id  = Column(Integer, ForeignKey("football_match.match_id"), nullable=False)
    team_side = Column(String(10), nullable=False)
    mean      = Column(Float, nullable=True)
    std       = Column(Float, nullable=True)
    shannon   = Column(Float, nullable=True)
    cv        = Column(Float, nullable=True)
    gini      = Column(Float, nullable=True)
    hhi       = Column(Float, nullable=True)

    match = relationship("FootballMatch", back_populates="match_stats")

    @classmethod
    def create_or_update(cls, session, match_id: int, side: str, data: dict) -> "MatchStats":
        """Insert or update a ``MatchStats`` row for one match side.

        Looks up an existing ``(match_id, team_side)`` row; if none exists a new
        instance is created and added to the session. The six diversity metrics
        (mean/std/shannon/cv/gini/hhi) are then written from ``data`` and the
        session is flushed.

        Args:
            session (sqlalchemy.orm.Session): Active database session.
            match_id (int): ``FootballMatch.match_id`` the stats belong to.
            side (str): Team side, 'home' or 'away'.
            data (dict): Mapping of metric name to value; only the recognised
                keys are written, others are ignored.

        Returns:
            MatchStats: The persisted (inserted or updated) stats row.
        """
        obj = session.execute(
            select(cls).where(cls.match_id == match_id, cls.team_side == side)
        ).scalar_one_or_none()
        if not obj:
            obj = cls(match_id=match_id, team_side=side)
            session.add(obj)
        for field in ("mean", "std", "shannon", "cv", "gini", "hhi"):
            setattr(obj, field, data.get(field))
        session.flush()
        return obj


class MatchForm(db.Model):
    """Per-team, per-match form and head-to-head summary.

    Captures recent form (last-3/5/season points and goals), the team's league
    placement, and the running head-to-head record against the opponent
    (matches/wins/draws/losses/goals/last-5 points) as of this match. One row
    exists per ``(match_id, team_side)``.
    """
    __tablename__ = "match_form"

    form_id           = Column(Integer, primary_key=True)
    match_id          = Column(Integer, ForeignKey("football_match.match_id"))
    team_side         = Column(String)
    form_last_3       = Column(Float)
    form_last_5       = Column(Float)
    form_season       = Column(Float)
    goals_last_3      = Column(Float)
    goals_last_5      = Column(Float)
    goals_season      = Column(Float)
    team_placement    = Column(Integer)
    h2h_matches       = Column(Integer, nullable=True)
    h2h_wins          = Column(Integer, nullable=True)
    h2h_draws         = Column(Integer, nullable=True)
    h2h_losses        = Column(Integer, nullable=True)
    h2h_goals_for     = Column(Integer, nullable=True)
    h2h_goals_against = Column(Integer, nullable=True)
    h2h_last_5_points = Column(Integer, nullable=True)

    match = relationship("FootballMatch", back_populates="form_data")
