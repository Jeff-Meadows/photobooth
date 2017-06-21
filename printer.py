# coding: utf-8

from __future__ import unicode_literals, division
import math
import os
from PIL import Image
from Queue import Queue, Empty
import subprocess
from tempfile import gettempdir
from threading import Thread
from uuid import uuid4

from conf import Configuration


class Printer(object):
    def __init__(self, queue):
        self._image_dir = gettempdir()
        self._images = []
        self._incoming_image_queue = queue
        self._processed_image_queue = Queue()
        self._printer_thread = Thread(target=self._process_print_queue)
        self._printer_thread.daemon = True
        self._printer_thread.start()
        self._shutting_down = False

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
                self.print_images(incoming_images)
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
        os.remove(image_sys_path)

    def print_images(self, image_sys_paths):
        thumbnail_width, thumbnail_height = 870, 525
        desired_ratio = thumbnail_width / thumbnail_height
        images = [Image.open(i[2]) for i in image_sys_paths]
        resized_images = []
        for image in images:
            x, y = image.size
            ratio = x / y
            if ratio < desired_ratio:
                if x < thumbnail_width:
                    image = image.resize((thumbnail_width, int(thumbnail_width / x * y)))
                    x, y = image.size
                    ratio = x / y
                # image too tall
                desired_height = x / desired_ratio
                height_difference = (y - desired_height) / 2
                resized_image = image.crop(
                    (0, int(math.floor(height_difference)), x, y - int(math.floor(height_difference))),
                )
            else:
                resized_image = image
            resized_image.thumbnail((thumbnail_width, thumbnail_height))
            resized_images.append(resized_image)
        image_1, image_2, image_3, image_4 = resized_images
        image = Image.open(Configuration.TEMPLATE_SYS_PATH)
        margin, gap = 25, 10
        image.paste(image_1, (margin, margin))
        image.paste(image_2, (margin + thumbnail_width + gap, margin))
        image.paste(image_3, (margin, margin + thumbnail_height + gap))
        image.paste(image_4, (margin + thumbnail_width + gap, margin + thumbnail_height + gap))
        image_sys_path = os.path.join(self._image_dir, 'photobooth-final-{}.jpg'.format(uuid4().hex))
        self._images.append(image_sys_path)
        image.save(image_sys_path)
        self._processed_image_queue.put(image_sys_path)


if __name__ == '__main__':
    from Queue import Queue
    import sys
    queue = Queue()
    Printer(queue).print_images([(None, None, a) for a in sys.argv[1:]])
    queue.join()
