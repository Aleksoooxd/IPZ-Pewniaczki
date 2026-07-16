from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import relationship, backref

from ..db import db


class TeamElo(db.Model):
    """Season-end ELO rating snapshot for a team.

    One row per ``(team_id, season_id)`` holding the team's final rating and the
    date it was last updated. The unique constraint keeps the table bounded to
    roughly teams x seasons rows rather than two rows per match.
    """
    __tablename__ = "team_elo"

    elo_id       = Column(Integer, primary_key=True)
    team_id      = Column(Integer, ForeignKey("team.team_id"),   nullable=False)
    season_id    = Column(Integer, ForeignKey("season.season_id"), nullable=False)
    rating       = Column(Float,   nullable=False, default=1500.0)
    last_updated = Column(Date,    nullable=False)

    __table_args__ = (
        # One ELO snapshot per team per season (season-end rating). Keeps the
        # table bounded (~teams x seasons rows) instead of 2 rows per match.
        db.UniqueConstraint('team_id', 'season_id', name='uq_team_elo_team_season'),
    )

    team   = relationship("Team",   backref=backref("elo_ratings",  order_by="TeamElo.last_updated"))
    season = relationship("Season", backref=backref("elo_ratings",  order_by="TeamElo.last_updated"))
