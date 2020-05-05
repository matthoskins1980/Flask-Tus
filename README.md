# Flask-Tus
Flask Extension implementing the Tus.io server protocol

As of May, 2020, I am using this code in a production enterprise application
running on Google Compute Engine with Uppy as the frontend (Javascript client).
YMMV, but I'm confident this _can_ work. The code could use some work, but it
does in fact work.

## Prerequisites (redis)

Currently flask-tus is reliant on a local redis server.  This is used for caching information about
uploads in progress.  It is on the roadmap to remove this dependancy.  You must install the redis python package
for this extension to work.

```
pip install redis
```

## Installation

Installation from source (this repository)

```
python setup.py install
```

Installation from PyPi repository (recommended for latest stable release)

```
pip install Flask-Tus
```

## Usage

### demo.py

```python
from flask import Flask, render_template, send_from_directory
from flask_tus import tus_manager
import os

app = Flask(__name__)
tm = tus_manager(app, upload_url='/file-upload', upload_folder='uploads/')
```

tus_manager() registers two new url endpoint /file-upload and /file-upload/\<resource\>.  You can not define views for those
urls in your app.  Simply use any tus client and point it to  /file-upload as the endpoint

```
Building (local instructions for me
```

1. python setup.py sdist
2. twine upload <filecreated>
