# coding: utf-8

from __future__ import unicode_literals
from time import sleep
from bottle import Bottle, request, response, static_file
from datetime import datetime, timedelta
import os
import random
from camera import Camera
from printer import Printer


app = Bottle()
camera = Camera()
printer = Printer()


@app.get('/evf')
def evf_video():
    try:
        seconds = int(request.params.get('seconds', 5))
        stop_time = datetime.now() + timedelta(seconds=seconds)
        response.content_type = 'multipart/x-mixed-replace; boundary=frame'
        with camera.live_view() as view:
            while datetime.now() < stop_time:
                filename = camera.get_evf_frame(view)
                if filename:
                    with open(filename, 'rb') as evf_file:
                        frame = evf_file.read()
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    except Exception as ex:
        import traceback
        traceback.print_exc()
        raise


@app.post('/photo')
def take_image():
    return {'ticket': camera.shoot(request.forms.get('name'), request.forms.get('email'))}


@app.get('/photo')
def get_image():
    ticket = request.params.get('ticket', 0)
    while len(camera.photos) < int(ticket):
        sleep(0.01)
    return static_file(camera.filename, root='image')


@app.post('/print')
def print_images():
    printer.print_images(camera.photos[-4:])
    return {}


@app.get('/')
def index():
    return static_file('index.html', root='')


@app.get('/random')
def random_image():
    return static_file(random.choice(os.listdir('image')), root='image')


@app.get('/static/<filename>')
def static(filename):
    return static_file(filename, root='static')


with camera.run():
    app.run(debug=True)
