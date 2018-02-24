import json
import os
import requests

from celery import chain
from facebook import GraphAPI, get_user_from_cookie
from flask import Flask, jsonify, render_template, request

from .helpers import find_closest, make_celery, save_file
from .models import Verification, db


FB_ID = os.getenv('FB_ID')
FB_SECRET = os.getenv('FB_SECRET')
OCR_KEY = os.getenv('OCR_KEY')
FACE_KEY = os.getenv('FACE_KEY')

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'media/')

app = Flask(__name__)
app.config.update(
    CELERY_RESULT_BACKEND='redis://localhost:6379',
    CELERY_BROKER_URL='redis://localhost:6379',
    SQLALCHEMY_DATABASE_URI='sqlite:///test.db',
    UPLOAD_FOLDER=UPLOAD_FOLDER
)

celery = make_celery(app)
db.init_app(app)


@celery.task()
def verify_photo(verification_id):
    verification = Verification.query.filter_by(id=verification_id).first()
    base_url = 'https://westcentralus.api.cognitive.microsoft.com/face/v1.0/'
    detect_url = base_url + 'detect'
    verify_url = base_url + 'verify'
    fileup_headers = {
        'Ocp-Apim-Subscription-Key': FACE_KEY,
        'Content-Type': 'application/octet-stream'
    }
    headers = {
        'Ocp-Apim-Subscription-Key': FACE_KEY,
    }

    with open(verification.id_image, 'rb') as f:
        id_face = requests.post(detect_url, headers=fileup_headers, data=f).json()

    with open(verification.fb_picture, 'rb') as f:
        fb_face = requests.post(detect_url, headers=fileup_headers, data=f).json()

    result = {
        'id_face': id_face,
        'fb_face': fb_face,
        'verify': None
    }

    print(id_face, fb_face)
    if id_face and fb_face:
        data = {
            'faceId1': id_face[0]['faceId'],
            'faceId2': fb_face[0]['faceId'],
        }
        resp = requests.post(verify_url, headers=headers, json=data).json()
        result['verify'] = resp

    verification.face_verify_result = json.dumps(result)

    db.session.add(verification)
    db.session.commit()


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

    fb_picture = graph.get_object(id='me/picture', type='large')
    filename = '{}/fb_pic_{}.jpg'.format(UPLOAD_FOLDER, verification_id)
    with open(filename, 'wb') as f:
        f.write(fb_picture['data'])

    verification.fb_picture = filename

    db.session.add(verification)
    db.session.commit()

    return verification_id


@celery.task()
def ocr_data(verification_id):
    print("OCR {}".format(verification_id))
    base_url = 'https://westcentralus.api.cognitive.microsoft.com/vision/v1.0/'
    ocr_url = base_url + 'ocr'
    headers = {
        'Ocp-Apim-Subscription-Key': OCR_KEY,
        'Content-Type': 'application/octet-stream'
    }
    params = {'language': 'en'}

    verification = Verification.query.filter_by(id=verification_id).first()

    with open(verification.id_image, 'rb') as f:
        response = requests.post(ocr_url, params=params, headers=headers,
                                 data=f)

    data = response.json()
    words = []
    for region in data['regions']:
        for line in region['lines']:
            for word in line['words']:
                words.append(word['text'])

    print(words)
    fname_closest = find_closest(verification.first_name, words)
    lname_closest = find_closest(verification.last_name, words)
    result = {
            'first_name': {
                'text': verification.first_name,
                'closest': fname_closest['word'],
                'distance': fname_closest['distance']
            },
            'last_name': {
                'text': verification.last_name,
                'closest': lname_closest['word'],
                'distance': lname_closest['distance']
            },
    }

    verification.ocr_data = json.dumps(data)
    verification.ocr_result = json.dumps(result)

    db.session.add(verification)
    db.session.commit()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/verify/', methods=['POST'])
def verify():
    result = get_user_from_cookie(
        cookies=request.cookies, app_id=FB_ID, app_secret=FB_SECRET
    )
    data = request.form
    file = request.files['identification']
    file_path = save_file(file, app.config['UPLOAD_FOLDER'])

    verification = Verification(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        birthday=data['birthday'],
        id_image=file_path
    )

    db.session.add(verification)
    db.session.flush()  # just to get the id

    chain(
        verify_data.s(result['access_token'], verification.id),
        verify_photo.s()
    )()
    ocr_data.delay(verification.id)

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
        'ocr_result': None,
        'face_verify_result': None
    }
    if verification.fb_result:
        result['fb_result'] = json.loads(verification.fb_result)
    if verification.ocr_result:
        result['ocr_result'] = json.loads(verification.ocr_result)
    if verification.face_verify_result:
        result['face_verify_result'] = json.loads(verification.face_verify_result)

    return jsonify(result)


@app.route('/db/refresh')
def db_create():
    db.drop_all()
    db.create_all()
    return 'ok'
