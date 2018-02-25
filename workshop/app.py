import json
import os

from facebook import GraphAPI, get_user_from_cookie
from flask import Flask, jsonify, render_template, request

from .helpers import make_celery
from .models import Verification, db


FB_ID = os.getenv('FB_ID')
FB_SECRET = os.getenv('FB_SECRET')

app = Flask(__name__)
app.config.update(
    CELERY_RESULT_BACKEND='redis://localhost:6379',
    CELERY_BROKER_URL='redis://localhost:6379',
    SQLALCHEMY_DATABASE_URI='sqlite:///test.db',
)

celery = make_celery(app)
db.init_app(app)


@celery.task()
def verify_data(access_token, verification_id):
    print('VERIFY {}', verification_id)
    VERIFICATION_ATTR = ['first_name', 'last_name', 'email', 'birthday']

    graph = GraphAPI(access_token=access_token, version='2.11')
    fb_data = graph.get_object(id='me',
                               fields='first_name,last_name,email,birthday')
    verification = Verification.query.filter_by(id=verification_id).first()

    result = {}
    for attr in VERIFICATION_ATTR:
        result[attr] = getattr(verification, attr) == fb_data[attr]
    verification.fb_result = json.dumps(result)
    verification.fb_data = json.dumps(fb_data)

    db.session.add(verification)
    db.session.commit()

    return verification_id


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/verify/', methods=['POST'])
def verify():
    result = get_user_from_cookie(
        cookies=request.cookies, app_id=FB_ID, app_secret=FB_SECRET
    )
    data = request.form

    verification = Verification(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        birthday=data['birthday'],
    )

    db.session.add(verification)
    db.session.flush()  # just to get the id

    verify_data.delay(result['access_token'], verification.id)

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
        'fb_data': json.loads(verification.fb_data),
        'fb_result': None,
    }
    if verification.fb_result:
        result['fb_result'] = json.loads(verification.fb_result)

    return jsonify(result)


@app.route('/db/refresh')
def db_create():
    db.drop_all()
    db.create_all()
    return 'ok'
