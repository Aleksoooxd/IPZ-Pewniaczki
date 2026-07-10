from sqlalchemy import Column, Integer, String, ForeignKey, select
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError

from ..db import db


class Team(db.Model):
    __tablename__ = "team"

    team_id = Column(Integer, primary_key=True)
    name    = Column(String(100), unique=True)

    team_leagues  = relationship("TeamLeague", back_populates="team")
    home_matches  = relationship("FootballMatch", foreign_keys="[FootballMatch.home_team_id]", back_populates="home_team")
    away_matches  = relationship("FootballMatch", foreign_keys="[FootballMatch.away_team_id]", back_populates="away_team")


class League(db.Model):
    __tablename__ = "league"

    league_id = Column(Integer, primary_key=True)
    code      = Column(String(30), unique=True)

    team_leagues  = relationship("TeamLeague", back_populates="league")
    matches       = relationship("FootballMatch", back_populates="league")
    future_match  = relationship("FutureMatch",   back_populates="league")


class Season(db.Model):
    __tablename__ = "season"

    season_id = Column(Integer, primary_key=True)
    name      = Column(String(10), unique=True)

    team_leagues  = relationship("TeamLeague", back_populates="season")
    matches       = relationship("FootballMatch", back_populates="season")
    future_match  = relationship("FutureMatch",   back_populates="season")


class TeamLeague(db.Model):
    __tablename__ = "team_league"

    team_league_id = Column(Integer, primary_key=True)
    team_id        = Column(Integer, ForeignKey("team.team_id"))
    league_id      = Column(Integer, ForeignKey("league.league_id"))
    season_id      = Column(Integer, ForeignKey("season.season_id"))

    team   = relationship("Team",   back_populates="team_leagues")
    league = relationship("League", back_populates="team_leagues")
    season = relationship("Season", back_populates="team_leagues")


def rename_team(old_name: str, new_name: str) -> bool:
    if not isinstance(old_name, str) or not isinstance(new_name, str):
        return False
    if not old_name.strip() or not new_name.strip():
        return False
    if old_name == new_name:
        return True

    team = db.session.execute(select(Team).where(Team.name == old_name)).scalar_one_or_none()
    if team is None:
        return False

    clash = db.session.execute(select(Team).where(Team.name == new_name)).scalar_one_or_none()
    if clash and clash.team_id != team.team_id:
        return False

    team.name = new_name
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False
