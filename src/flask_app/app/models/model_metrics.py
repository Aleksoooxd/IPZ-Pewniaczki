from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.orm import relationship

from ..db import db


class ModelMetrics(db.Model):
    """Record of a trained prediction model's evaluation run.

    Stores the model name, training timestamp, accuracy / log-loss on the held
    out test set, train/test sizes, the JSON-serialised feature list, and the
    checkpoint path. The ``notes`` column is free-form.
    """

    __tablename__ = "model_metrics"

    metric_id       = Column(Integer, primary_key=True)
    model_name      = Column(String,  nullable=False)
    trained_at      = Column(DateTime, server_default=func.now(), nullable=False)
    accuracy        = Column(Float,   nullable=True)
    log_loss        = Column(Float,   nullable=True)
    n_train         = Column(Integer, nullable=True)
    n_test          = Column(Integer, nullable=True)
    features        = Column(Text,    nullable=True)  # JSON list of feature names
    checkpoint_path = Column(String,  nullable=True)
    notes           = Column(Text,    nullable=True)
