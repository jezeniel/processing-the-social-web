from flask import Flask, jsonify, render_template, request

from .models import Verification, db


app = Flask(__name__)
app.config.update(
    CELERY_RESULT_BACKEND='redis://localhost:6379',
    CELERY_BROKER_URL='redis://localhost:6379',
    SQLALCHEMY_DATABASE_URI='sqlite:///test.db',
)

db.init_app(app)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/verify/', methods=['POST'])
def verify():
    data = request.form

    verification = Verification(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        birthday=data['birthday'],
    )

    db.session.add(verification)
    db.session.commit()
    return render_template('success.html', verification_id=verification.id)


@app.route('/verifications/<id>/')
def verifications(id):
    verification = Verification.query.filter_by(id=id).first()
    result = {
        'application_data': {
            'first_name': verification.first_name,
            'last_name': verification.last_name,
            'email': verification.email,
            'birthday': verification.birthday,
        },
    }
    return jsonify(result)


@app.route('/db/refresh')
def db_create():
    db.drop_all()
    db.create_all()
    return 'ok'
