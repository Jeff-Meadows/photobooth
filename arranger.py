# coding: utf-8

from __future__ import unicode_literals, absolute_import, division

import math
import os
from tempfile import gettempdir
from uuid import uuid4

from PIL import Image

from conf import Configuration


class Arranger(object):
    def __init__(self, queue):
        super(Arranger, self).__init__()
        self._image_dir = gettempdir()
        self._processed_image_queue = queue

    def print_images(self, image_sys_paths):
        thumbnail_width, thumbnail_height = 870, 440
        desired_ratio = thumbnail_width / thumbnail_height
        images = [Image.open(i) for i in image_sys_paths]
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
        top_margin = 150
        left_margin = 20
        gap_between_photos = 20
        image.paste(image_1, (left_margin, top_margin))
        image.paste(image_2, (left_margin + thumbnail_width + gap_between_photos, top_margin))
        image.paste(image_3, (left_margin, top_margin + thumbnail_height + gap_between_photos))
        image.paste(image_4, (left_margin + thumbnail_width + gap_between_photos, top_margin + thumbnail_height + gap_between_photos))
        image_sys_path = os.path.join(self._image_dir, 'photobooth-final-{}.jpg'.format(uuid4().hex))
        image.save(image_sys_path)
        self._processed_image_queue.put(image_sys_path)


if __name__ == '__main__':
    from Queue import Queue
    import sys
    queue = Queue()
    arranger = Arranger(queue)
    arranger.print_images([a for a in sys.argv[1:]])
    print queue.get()
