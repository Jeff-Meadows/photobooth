# coding: utf-8

from __future__ import unicode_literals, absolute_import

from contextlib import contextmanager
from Queue import Queue, Empty
from threading import Thread

from box import Box
from camera import EdsCamera as Camera
from printer import Printer


class App(object):
    def __init__(self):
        super(App, self).__init__()
        self._camera_queue = Queue()
        self._box_queue = Queue()
        self._printer_queue = Queue()
        self._box = Box(self._box_queue)
        self._camera = Camera(self._camera_queue)
        self._printer = Printer(self._printer_queue)
        self._shutting_down = False
        self._process_camera_queue_thread = Thread(target=self._process_camera_queue)
        self._process_camera_queue_thread.start()

    def photobooth_session(self):
        with self._camera.run():
            for _ in xrange(4):
                user_input = raw_input('Press enter to take a photo (or type quit to quit):')
                if user_input == 'quit':
                    self._shutting_down = True
                    self._printer.shutdown()
                    return
                else:
                    self._camera.shoot()

    def _process_camera_queue(self):
        while not self._shutting_down:
            try:
                photo = self._camera_queue.get(timeout=1)
            except Empty:
                continue
            self._box_queue.put(photo)
            self._printer_queue.put(photo)
            self._camera_queue.task_done()

    def shutdown(self):
        self._box.shutdown()
        self._printer.shutdown()


if __name__ == '__main__':
    app = App()
    app.photobooth_session()

