import json
import os
import requests

from facebook import GraphAPI, get_user_from_cookie
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from .helpers import make_celery
from .models import Verification, db


FB_ID = os.getenv('FB_ID')
FB_SECRET = os.getenv('FB_SECRET')
OCR_KEY = os.getenv('OCR_KEY')

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


def save_file(file):
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return path


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)

    # len(s1) >= len(s2)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_closest(text, words):
    closest_distance = None
    closest_word = None
    for word in words:
        distance = levenshtein(text.lower(), word.lower())
        if closest_distance is None or closest_distance > distance:
            closest_distance = distance
            closest_word = word
    return {'word': closest_word, 'distance': closest_distance}


@celery.task()
def verify_data(access_token, verification_id):
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


@celery.task()
def ocr_data(verification_id):
    print("OCR {}".format(verification_id))
    base_url = 'https://westcentralus.api.cognitive.microsoft.com/vision/v1.0/'
    ocr_url = base_url + 'ocr'
    headers = {'Ocp-Apim-Subscription-Key': OCR_KEY}
    params = {'language': 'en'}

    verification = Verification.query.filter_by(id=verification_id).first()

    files = {'file': open(verification.id_image, 'rb')}
    response = requests.post(ocr_url, params=params, headers=headers,
                             files=files)

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
    file_path = save_file(file)

    verification = Verification(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        birthday=data['birthday'],
        id_image=file_path
    )

    db.session.add(verification)
    db.session.flush()  # just to get the id

    verify_data.delay(result['access_token'], verification.id)
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
        'ocr_result': None
    }
    if verification.fb_result:
        result['fb_result'] = json.loads(verification.fb_result)
    if verification.ocr_result:
        result['ocr_result'] = json.loads(verification.ocr_result)
    return jsonify(result)


@app.route('/db/refresh')
def db_create():
    db.drop_all()
    db.create_all()
    return 'ok'
