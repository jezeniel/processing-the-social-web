from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Verification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    birthday = db.Column(db.String(255), nullable=False)
    fb_data = db.Column(db.Text, nullable=True)
    result = db.Column(db.Text, nullable=True)
