# Flask Crash Course

*crash_course/app.py*

```python
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)


@app.route('/page/<name>/')
def page(name):
    return render_template('hello.html', name=name)


@app.route('/api/get/<id>')
def index(id):
    return jsonify({'id': id})


@app.route('/api/post/', methods=['POST'])
def api():
    data = request.get_json()
    return jsonify(request_body=data)
```

*crash_course/templates/hello.html*

```html
<html>
    <body>
        <h1>Hello, {{name}}</h1>
    </body>
</html>
```

# Celery

## Flask Integration

```python
from celery import Celery
from flask import Flask, jsonify, request, render_template


def make_celery(app):
    celery = Celery(app.import_name,
                    broker=app.config['CELERY_BROKER_URL'],
                    backend=app.config['CELERY_RESULT_BACKEND'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery


app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)
celery = make_celery(app)


@celery.task()
def add(a, b):
    print(a + b)
    return a + b


@app.route('/page/<name>/')
def page(name):
    return render_template('hello.html', name=name)


@app.route('/api/get/<id>')
def index(id):
    return jsonify({'id': id})


@app.route('/api/post/', methods=['POST'])
def api():
    data = request.get_json()
    return jsonify(request_body=data)


@app.route('/api/add/<a>/<b>/')
def add_api(a, b):
    result = add.delay(a, b)
    return jsonify({'result': result.get()})
```

## Better Approach

```python
from celery import Celery
from celery.result import AsyncResult
from flask import Flask, jsonify, request, render_template


def make_celery(app):
    celery = Celery(app.import_name,
                    broker=app.config['CELERY_BROKER_URL'],
                    backend=app.config['CELERY_RESULT_BACKEND'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery


app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)
celery = make_celery(app)


@celery.task()
def add(a, b):
    print(a + b)
    return a + b


@app.route('/page/<name>/')
def page(name):
    return render_template('hello.html', name=name)


@app.route('/api/get/<id>')
def index(id):
    return jsonify({'id': id})


@app.route('/api/post/', methods=['POST'])
def api():
    data = request.get_json()
    return jsonify(request_body=data)


## We changed the api above
@app.route('/api/add/<a>/<b>/')
def add_api(a, b):
    result = add.delay(a, b)
    return jsonify({'task_id': result.id})


@app.route('/api/results/<task_id>')
def results_api(task_id):
    result = AsyncResult(id=task_id, app=celery)
    return jsonify({'status': result.status, 'result': result.result})
```

