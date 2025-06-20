from . import db


class TrackedTime(db.Model):
    __tablename__ = "tracked_time"

    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String, nullable=False)