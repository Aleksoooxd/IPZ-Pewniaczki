from . import db

class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    hire_date = db.Column(db.Date)
    department = db.Column(db.String(50))
    salary = db.Column(db.Numeric(10, 2))