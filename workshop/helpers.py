import os

from celery import Celery
from werkzeug.utils import secure_filename


def make_celery(flask_app):
    celery = Celery(
        flask_app.import_name,
        backend=flask_app.config['CELERY_RESULT_BACKEND'],
        broker=flask_app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(flask_app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


def save_file(file, path):
    filename = secure_filename(file.filename)
    path = os.path.join(path, filename)
    file.save(path)
    return path


def levenshtein(s1, s2):
    ''' find the edit distance between two strings '''
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
    ''' find the closest distance between the `text` and a list of words '''
    closest_distance = None
    closest_word = None
    for word in words:
        distance = levenshtein(text.lower(), word.lower())
        if closest_distance is None or closest_distance > distance:
            closest_distance = distance
            closest_word = word
    return {'word': closest_word, 'distance': closest_distance}
