from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from ..db import db


class Predicted(db.Model):
    """A prediction for an already-played match.

    Stores the model's predicted outcome (``'H'``/``'D'``/``'A'``) and its
    confidence for a :class:`FootballMatch`.
    """
    __tablename__ = "predicted"

    prediction_id    = Column(Integer, primary_key=True)
    match_id         = Column(Integer, ForeignKey("football_match.match_id"))
    predicted_result = Column(String)
    confidence       = Column(Float)

    match = relationship("FootballMatch", back_populates="predictions")


class PredictedFuture(db.Model):
    """A prediction for a not-yet-played (:class:`FutureMatch`) match.

    Stores the model's predicted outcome and confidence for an upcoming fixture.
    """
    __tablename__ = "predicted_future"

    prediction_id    = Column(Integer, primary_key=True)
    match_id         = Column(Integer, ForeignKey("future_match.match_id"))
    predicted_result = Column(String)
    confidence       = Column(Float)

    future_match = relationship("FutureMatch", back_populates="future_predictions")
