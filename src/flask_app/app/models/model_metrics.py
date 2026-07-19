from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.orm import relationship

from ..db import db


class ModelMetrics(db.Model):
    """Record of a trained prediction model's evaluation run.

    Stores the model name, training timestamp, accuracy / log-loss on the held
    out test set, train/test sizes, the JSON-serialised feature list, and the
    checkpoint path. The ``notes`` column is free-form.

    Beyond the headline accuracy / log-loss, per-class metrics (recall /
    precision / support for each of H / D / A), the macro-F1 score, and the 3x3
    confusion matrix are persisted (as JSON text) so the dashboard can show a
    full breakdown without re-running the model.
    """

    __tablename__ = "model_metrics"

    metric_id       = Column(Integer, primary_key=True)
    model_name      = Column(String,  nullable=False)
    trained_at      = Column(DateTime, server_default=func.now(), nullable=False)
    accuracy        = Column(Float,   nullable=True)
    log_loss        = Column(Float,   nullable=True)
    baseline_accuracy = Column(Float, nullable=True)  # ELO-favourite naive baseline
    macro_f1        = Column(Float,   nullable=True)
    per_class       = Column(Text,    nullable=True)  # JSON: {"H":{recall,precision,support},...}
    confusion_matrix = Column(Text,   nullable=True)  # JSON: [[H,H,H],[D,D,D],[A,A,A]] (true x pred)
    n_train         = Column(Integer, nullable=True)
    n_test          = Column(Integer, nullable=True)
    features        = Column(Text,    nullable=True)  # JSON list of feature names
    checkpoint_path = Column(String,  nullable=True)
    notes           = Column(Text,    nullable=True)
