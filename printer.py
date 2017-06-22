# coding: utf-8

from __future__ import unicode_literals, division

from Queue import Empty
import subprocess
from threading import Thread

from arranger import Arranger


class Printer(object):
    def __init__(self, queue):
        self._incoming_image_queue = queue
        self._processed_image_queue = Queue()
        self._arranger = Arranger(self._processed_image_queue)
        self._shutting_down = False
        self._printer_thread = Thread(target=self._process_print_queue)
        self._printer_thread.daemon = True
        self._printer_thread.start()
        self._processor_thread = Thread(target=self._process_incoming_queue)
        self._processor_thread.daemon = True
        self._processor_thread.start()

    def shutdown(self):
        self._incoming_image_queue.join()
        self._processed_image_queue.join()
        self._shutting_down = True

    def _process_incoming_queue(self):
        incoming_images = []
        while not self._shutting_down:
            try:
                image = self._incoming_image_queue.get(timeout=1)
            except Empty:
                continue
            incoming_images.append(image)
            if len(incoming_images) == 4:
                print 'printing', incoming_images
                self._arranger.print_images(incoming_images)
                del incoming_images[:]
            self._incoming_image_queue.task_done()

    def _process_print_queue(self):
        while True:
            self._print_photo(self._processed_image_queue.get())
            self._processed_image_queue.task_done()

    def _print_photo(self, image_sys_path):
        import shutil
        shutil.copy(image_sys_path, 'image/')
        if sys.platform == 'darwin':
            subprocess.call([
                'lp',
                '-d',
                'Canon_mini260',
                '-o',
                'media=4x6.FullBleed',
                '-o',
                'CNIJMediaType=29',
                image_sys_path,
            ])
        else:
            subprocess.call(['lib/ImagePrint.exe', image_sys_path])


if __name__ == '__main__':
    from Queue import Queue
    import sys
    queue = Queue()
    printer = Printer(queue)
    for a in sys.argv[1:]:
        queue.put(a)
    printer.shutdown()
