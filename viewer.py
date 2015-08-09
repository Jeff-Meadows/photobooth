# coding: utf-8

from __future__ import unicode_literals

from bottle import Bottle, static_file
import os
from box import Box


app = Bottle()
box = Box()


@app.get('/')
def index():
    return static_file('viewer.html', root='')


@app.get('/ajax/files')
def files():
    return {
        'files': [f.id for f in box.list_files()]
    }


@app.get('/images/<filename>')
def image(filename):
    sys_path = os.path.join('image', filename)
    if not os.path.exists(sys_path):
        file_id, _ = os.path.splitext(filename)
        box.download_photo(file_id, sys_path)
    return static_file(filename, root='image')


@app.get('/static/<filename:path>')
def static(filename):
    return static_file(filename, root='static')


app.run(debug=True)
