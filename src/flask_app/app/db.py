import os

import pandas as pd
import sqlalchemy
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from src.flask_app.app import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app, session_options={'autoflush': False})

from sqlalchemy import create_engine, Column, Integer, String, Date, Float, Boolean, ForeignKey, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref


class Team(db.Model):
    __tablename__ = 'team'

    team_id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)

    team_leagues = relationship("TeamLeague", back_populates="team")
    home_matches = relationship("FootballMatch", foreign_keys="[FootballMatch.home_team_id]",back_populates="home_team")
    away_matches = relationship("FootballMatch", foreign_keys="[FootballMatch.away_team_id]",back_populates="away_team")
    team_values = relationship("TeamValue", back_populates="team")


class League(db.Model):
    __tablename__ = 'league'

    league_id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True)

    team_leagues = relationship("TeamLeague", back_populates="league")
    matches = relationship("FootballMatch", back_populates="league")
    future_match = relationship("FutureMatch", back_populates="league")


class Season(db.Model):
    __tablename__ = 'season'

    season_id = Column(Integer, primary_key=True)
    name = Column(String(10), unique=True)

    team_leagues = relationship("TeamLeague", back_populates="season")
    matches = relationship("FootballMatch", back_populates="season")
    team_values = relationship("TeamValue", back_populates="season")
    future_match = relationship("FutureMatch", back_populates="season")

class TeamLeague(db.Model):
    __tablename__ = 'team_league'

    team_league_id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('team.team_id'))
    league_id = Column(Integer, ForeignKey('league.league_id'))
    season_id = Column(Integer, ForeignKey('season.season_id'))

    team = relationship("Team", back_populates="team_leagues")
    league = relationship("League", back_populates="team_leagues")
    season = relationship("Season", back_populates="team_leagues")


class TeamValue(db.Model):
    __tablename__ = 'team_value'

    value_id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('team.team_id'))
    season_id = Column(Integer, ForeignKey('season.season_id'))
    value = Column(Float)

    team = relationship("Team", back_populates="team_values")
    season = relationship("Season", back_populates="team_values")


class FootballMatch(db.Model):
    __tablename__ = 'football_match'

    match_id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey('league.league_id'))
    season_id = Column(Integer, ForeignKey('season.season_id'))
    date = Column(Date)
    home_team_id = Column(Integer, ForeignKey('team.team_id'))
    away_team_id = Column(Integer, ForeignKey('team.team_id'))
    result = Column(String)
    home_matchday = Column(Integer)
    away_matchday = Column(Integer)
    home_elo = Column(Float, nullable=True)
    away_elo = Column(Float, nullable=True)
    home_elo_change = Column(Float, nullable=True)
    away_elo_change = Column(Float, nullable=True)
    fthg = Column(Integer)
    ftag = Column(Integer)
    home_value_id = Column(Integer, ForeignKey('team_value.value_id'))
    away_value_id = Column(Integer, ForeignKey('team_value.value_id'))
    is_surprise = Column(Boolean)
    is_suprise_h = Column(Boolean)
    is_suprise_d = Column(Boolean)
    is_suprise_a = Column(Boolean)
    consensus = Column(String)

    league = relationship("League", back_populates="matches")
    season = relationship("Season", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    home_value_ref = relationship("TeamValue", foreign_keys=[home_value_id])
    away_value_ref = relationship("TeamValue", foreign_keys=[away_value_id])
    match_stats = relationship("MatchStats", back_populates="match")
    form_data = relationship("MatchForm", back_populates="match")
    predictions = relationship("Predicted", back_populates="match")

class FutureMatch(db.Model):
    __tablename__ = 'future_match'
    match_id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey('league.league_id'))
    season_id = Column(Integer, ForeignKey('season.season_id'))
    home_matchday = Column(Integer)
    date = Column(Date)
    time = Column(String(5))
    home_team_id = Column(Integer, ForeignKey('team.team_id'))
    away_team_id = Column(Integer, ForeignKey('team.team_id'))

    league = relationship("League", back_populates="future_match")
    season = relationship("Season", back_populates="future_match")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    future_predictions = relationship("PredictedFuture", back_populates="future_match")

class MatchStats(db.Model):
    __tablename__ = 'match_stats'

    stat_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('football_match.match_id'), nullable=False)
    team_side = Column(String(10), nullable=False)

    mean = Column(Float, nullable=True)
    std = Column(Float, nullable=True)
    shannon = Column(Float, nullable=True)
    cv = Column(Float, nullable=True)
    gini = Column(Float, nullable=True)
    hhi = Column(Float, nullable=True)

    match = relationship("FootballMatch", back_populates="match_stats")

    @classmethod
    def create_or_update_stats(cls, session, match_id, side, stats_data):
        stats = session.execute(
            select(cls)
            .where(cls.match_id == match_id, cls.team_side == side)
        ).scalar_one_or_none()

        if not stats:
            stats = cls(match_id=match_id, team_side=side)
            session.add(stats)
        stats.mean = stats_data.get('mean')
        stats.std = stats_data.get('std')
        stats.shannon = stats_data.get('shannon')
        stats.cv = stats_data.get('cv')
        stats.gini = stats_data.get('gini')
        stats.hhi = stats_data.get('hhi')

        session.flush()
        return stats

class MatchForm(db.Model):
    __tablename__ = 'match_form'

    form_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('football_match.match_id'))
    team_side = Column(String)
    form_last_3 = Column(Float)
    form_last_5 = Column(Float)
    form_season = Column(Float)
    goals_last_3 = Column(Float)
    goals_last_5 = Column(Float)
    goals_season = Column(Float)
    team_placement = Column(Integer)
    h2h_matches = db.Column(db.Integer, nullable=True)
    h2h_wins = db.Column(db.Integer, nullable=True)
    h2h_draws = db.Column(db.Integer, nullable=True)
    h2h_losses = db.Column(db.Integer, nullable=True)
    h2h_goals_for = db.Column(db.Integer, nullable=True)
    h2h_goals_against = db.Column(db.Integer, nullable=True)
    h2h_last_5_points = db.Column(db.Integer, nullable=True)
    match = relationship("FootballMatch", back_populates="form_data")


class Predicted(db.Model):
    __tablename__ = 'predicted'

    prediction_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('football_match.match_id'))
    predicted_result = Column(String)
    confidence = Column(Float)

    match = relationship("FootballMatch", back_populates="predictions")
class TeamElo(db.Model):
    __tablename__ = 'team_elo'

    elo_id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('team.team_id'), nullable=False)
    rating = Column(Float, nullable=False, default=1500.0)
    last_updated = Column(Date, nullable=False)

    team = relationship("Team", backref=backref("elo_ratings", order_by=last_updated))
class PredictedFuture(db.Model):
    __tablename__ = 'predicted_future'

    prediction_id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('future_match.match_id'))
    predicted_result = Column(String)
    confidence = Column(Float)

    future_match = relationship("FutureMatch", back_populates="future_predictions")

if __name__ == "__main__":
    with app.app_context():
        #db.drop_all()
        db.create_all()
    app.run(debug=True)