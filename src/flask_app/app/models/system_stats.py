from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import db


class SystemStats(db.Model):
    __tablename__ = "system_stats"

    stat_id = Column(Integer, primary_key=True)
    recorded_at = Column(DateTime, server_default=func.now(), nullable=False)

    # --- Czasy wykonania ---
    scraping_time = Column(Float, nullable=True)
    elo_calc_time = Column(Float, nullable=True)
    prediction_time = Column(Float, nullable=True)

    # --- Liczniki ---
    teams_count = Column(Integer, nullable=True)
    seasons_count = Column(Integer, nullable=True)
    leagues_count = Column(Integer, nullable=True)
    matches_count = Column(Integer, nullable=True)
    future_matches_count = Column(Integer, nullable=True)

    # --- Rekordy ---
    highest_elo_id = Column(Integer, ForeignKey("team_elo.elo_id"), nullable=True)
    lowest_elo_id = Column(Integer, ForeignKey("team_elo.elo_id"), nullable=True)
    highest_goal_match_id = Column(Integer, ForeignKey("football_match.match_id"), nullable=True)


    biggest_upset_match_id = Column(Integer, ForeignKey("football_match.match_id"), nullable=True)

    biggest_upset_confidence = Column(Float, nullable=True)
    biggest_upset_predicted = Column(db.String(1), nullable=True)
    biggest_upset_actual = Column(db.String(1), nullable=True)

    highest_elo = relationship("TeamElo", foreign_keys=[highest_elo_id])
    lowest_elo = relationship("TeamElo", foreign_keys=[lowest_elo_id])
    highest_goal_match = relationship("FootballMatch", foreign_keys=[highest_goal_match_id])
    biggest_upset_match = relationship("FootballMatch", foreign_keys=[biggest_upset_match_id])