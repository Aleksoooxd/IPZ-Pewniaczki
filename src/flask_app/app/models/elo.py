from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import relationship, backref

from ..db import db


class TeamElo(db.Model):
    __tablename__ = "team_elo"

    elo_id       = Column(Integer, primary_key=True)
    team_id      = Column(Integer, ForeignKey("team.team_id"),   nullable=False)
    season_id    = Column(Integer, ForeignKey("season.season_id"), nullable=False)
    rating       = Column(Float,   nullable=False, default=1500.0)
    last_updated = Column(Date,    nullable=False)

    team   = relationship("Team",   backref=backref("elo_ratings",  order_by="TeamElo.last_updated"))
    season = relationship("Season", backref=backref("elo_ratings",  order_by="TeamElo.last_updated"))
