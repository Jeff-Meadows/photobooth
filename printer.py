# coding: utf-8

from __future__ import unicode_literals, division
import math
import os
from PIL import Image
from Queue import Queue
import subprocess
from tempfile import gettempdir
from threading import Thread


class Printer(object):
    def __init__(self):
        self._image_dir = gettempdir()
        self._images = []
        self._image_queue = Queue()
        self._printer_thread = Thread(target=self._process_queue)
        self._printer_thread.daemon = True
        self._printer_thread.start()

    def _process_queue(self):
        while True:
            self._print_photo(self._image_queue.get())

    def _print_photo(self, image_sys_path):
        import shutil
        shutil.copy(image_sys_path, '.')
        subprocess.call(['ImagePrint.exe', image_sys_path])
        os.remove(image_sys_path)

    def print_images(self, image_sys_paths):
        thumbnail_width, thumbnail_height = 570, 725
        desired_ratio = thumbnail_width / thumbnail_height
        images = [Image.open(i[2]) for i in image_sys_paths]
        resized_images = []
        for image in images:
            x, y = image.size
            print image.size
            ratio = x / y
            if ratio < desired_ratio:
                if x < thumbnail_width:
                    image = image.resize((thumbnail_width, int(thumbnail_width / x * y)))
                    x, y = image.size
                    print image.size
                    ratio = x / y
                # image too tall
                desired_height = x / desired_ratio
                height_difference = (y - desired_height) / 2
                resized_image = image.crop(
                    (0, int(math.floor(height_difference)), x, y - int(math.floor(height_difference))),
                )
                print (0, int(math.floor(height_difference)), x, y - int(math.floor(height_difference)))
                print resized_image.size
            else:
                resized_image = image
            resized_image.thumbnail((thumbnail_width, thumbnail_height))
            print resized_image.size
            resized_images.append(resized_image)
        image_1, image_2, image_3, image_4 = resized_images
        image = Image.open('photobooth.png')
        margin, gap = 25, 10
        image.paste(image_1, (margin, margin))
        image.paste(image_2, (margin + thumbnail_width + gap, margin))
        image.paste(image_3, (margin, margin + thumbnail_height + gap))
        image.paste(image_4, (margin + thumbnail_width + gap, margin + thumbnail_height + gap))
        image_sys_path = os.path.join(self._image_dir, '{}.jpg'.format(len(self._images)))
        self._images.append(image_sys_path)
        image.save(image_sys_path)
        self._image_queue.put(image_sys_path)


if __name__ == '__main__':
    import sys
    Printer().print_images([(None, None, a) for a in sys.argv[1:]])
    import time
    time.sleep(1)
