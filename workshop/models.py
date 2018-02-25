from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Verification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    birthday = db.Column(db.String(255), nullable=False)
    id_image = db.Column(db.String(255), nullable=False)

    fb_picture = db.Column(db.Text, nullable=True)
    fb_data = db.Column(db.Text, nullable=True)
    fb_result = db.Column(db.Text, nullable=True)

    ocr_result = db.Column(db.Text, nullable=True)
    ocr_data = db.Column(db.Text, nullable=True)
