import os

from flask import Flask, render_template

from .helpers import make_celery


FB_ID = os.getenv('FB_ID')
FB_SECRET = os.getenv('FB_SECRET')


app = Flask(__name__)
app.config.update(
    CELERY_RESULT_BACKEND='redis://localhost:6379',
    CELERY_BROKER_URL='redis://localhost:6379',
)
celery = make_celery(app)


@app.route('/')
def home():
    return render_template('index.html')
