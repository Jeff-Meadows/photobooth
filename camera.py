# coding: utf-8

from __future__ import unicode_literals
from contextlib import contextmanager
from ctypes import  c_int, c_uint, c_char_p, pointer, POINTER, byref, Structure, sizeof
#from ctypes import windll, WINFUNCTYPE
import os
from Queue import Queue
import subprocess
from threading import Thread
from box import Box


class EdsDirectoryItemInfo(Structure):
    __fields__ = [
        ('Size', c_uint),
        ('isFolder', c_int),
        ('GroupID', c_uint),
        ('Option', c_uint),
        ('szFileName', c_char_p),
        ('format', c_uint),
        ('dateTime', c_uint),
    ]


class Camera(object):
    DIR_ITEM_CONTEXT_CHANGED = 0x00000208

    def __init__(self):
        self._create_sdk()
        self._filename = None
        self._camera = None
        self._box = Box()
        self._photo_queue = Queue()
        self._photo_thread = Thread(target=self._process_queue)
        self._photo_thread.daemon = True
        self._photo_thread.start()
        self._name = None
        self._email = None
        self._photos = []

    def _create_sdk(self):
        self._sdk = windll.LoadLibrary(os.path.join(os.getcwd(), 'Windows', 'EDSDK', 'Dll', 'EDSDK.dll'))

    def _process_queue(self):
        while True:
            self._box.upload_photo(*self._photo_queue.get())

    @contextmanager
    def _initialized_sdk(self):
        self._sdk.EdsInitializeSDK()
        yield
        self._sdk.EdsTerminateSDK()

    @contextmanager
    def _camera_session(self):
        camera_list_ref = c_int()
        self._sdk.EdsGetCameraList(byref(camera_list_ref))
        self._camera = c_int()
        self._sdk.EdsGetChildAtIndex(byref(camera_list_ref), 0, byref(self._camera))
        self._sdk.EdsOpenSession(byref(self._camera))
        yield
        self._camera = None
        self._sdk.EdsCloseSession(byref(self._camera))

    @contextmanager
    def live_view(self):
        #EdsCreateEvfImageRef, EdsDownloadEvfImage, kEdsCameraCommand_DoEvfAf
        size = sizeof(c_int)
        self._sdk.EdsSetPropertyData(byref(self._camera), 0x00000501, 0, size, 1)  # Turn on EVF
        self._sdk.EdsSetPropertyData(byref(self._camera), 0x00000500, 0, size, 2)  # Set EVF device to PC
        self._sdk.EdsSetPropertyData(byref(self._camera), 0x0000050E, 0, size, 2)  # Set AF Mode to live face
        stream = c_int()
        self._sdk.EdsCreateFileStream('evf.jpg', 0, 1, byref(stream))
        #self._sdk.EdsCreateMemoryStream(0, byref(memory_stream))
        evf_image = c_int()
        self._sdk.EdsCreateEvfImageRef(byref(stream), byref(evf_image))
        yield evf_image
        self._sdk.EdsRelease(byref(evf_image))
        self._sdk.EdsRelease(byref(stream))
        self._sdk.EdsSetPropertyData(byref(self._camera), 0x00000500, 0, size, 1)  # Set EVF device to TFT
        self._sdk.EdsSetPropertyData(byref(self._camera), 0x00000501, 0, size, 0)  # Turn off EVF

    def get_evf_frame(self, evf_image):
        self._sdk.EdsDownloadEvfImage(byref(self._camera), byref(evf_image))
        return 'evf.jpg'

    def shoot(self, name, email):
        self._name = name
        self._email = email
        self._sdk.EdsSendCommand(byref(self._camera), 0x00000004, 3)  # Press shutter button completely
        self._sdk.EdsSendCommand(byref(self._camera), 0x00000004, 0)  # Press shutter button off
        return len(self._photos)

    @property
    def filename(self):
        return self._filename

    @property
    def photos(self):
        return self._photos

    @contextmanager
    def run(self):
        def release_callback(event_type, object_ref, _):
            if event_type == self.DIR_ITEM_CONTEXT_CHANGED:
                dir_info = EdsDirectoryItemInfo()
                self._sdk.EdsGetDirectoryItemInfo(byref(object_ref), pointer(dir_info))
                stream = c_int()
                self._filename = dir_info.szFileName
                self._sdk.EdsCreateFileStream(os.path.join('image', self._filename), 0, 1, byref(stream))
                self._sdk.EdsDownload(byref(dir_info), dir_info.Size, byref(stream))
                self._sdk.EdsDownloadComplete(byref(stream))
                self._sdk.EdsRelease(byref(stream))
                photo_info = (self._name, self._email, self._filename)
                self._photo_queue.put(photo_info)
                self._photos.append(photo_info)

        with self._initialized_sdk():
            with self._camera_session() as camera:
                callback_type = WINFUNCTYPE(c_uint, POINTER(c_int), POINTER(c_int))
                callback = callback_type(release_callback)
                self._sdk.EdsSetObjectEventHandler(byref(camera), self.DIR_ITEM_CONTEXT_CHANGED, callback, None)
                yield


class TestCamera(Camera):
    def __init__(self):
        self._test_images = ['image/video-streaming-{}.jpg'.format(i) for i in [1, 2, 3]]
        self._photos = []
        self._filename = 'video-streaming-1.jpg'

    @contextmanager
    def run(self):
        yield

    @contextmanager
    def live_view(self):
        yield

    def get_evf_frame(self, evf_image):
        import time
        return self._test_images[int(time.time()) % 3]

    def shoot(self, name, email):
        return -1


class MacbookCamera(Camera):
    def __init__(self):
        super(MacbookCamera, self).__init__()
        self._evf_thread = None

    def _create_sdk(self):
        pass

    @contextmanager
    def run(self):
        yield

    def _evf(self):
        self._evf_popen = subprocess.Popen(['../imagesnap', '-q', '-t', '0.1'], cwd='evf')

    @contextmanager
    def live_view(self):
        self._evf_thread = Thread(target=self._evf)
        self._evf_thread.start()
        yield
        self._evf_popen.terminate()
        self._evf_thread.join()
        for s in os.listdir('evf'):
            os.remove(os.path.join('evf', s))

    def get_evf_frame(self, evf_image):
        snapshots = sorted([s for s in os.listdir('evf') if s.startswith('snapshot')], reverse=True)
        if snapshots:
            last = snapshots[0]
            for s in snapshots[1:]:
                os.remove(os.path.join('evf', s))
            return os.path.join('evf', last)

    def shoot(self, name, email):
        self._name = name
        self._email = email
        self._filename = 'photobooth-{}.jpg'.format(len(self._photos))
        file_sys_path = os.path.join('image', self._filename)
        subprocess.call(['./imagesnap', '-q', '-w', '1', file_sys_path])
        photo_info = (self._name, self._email, file_sys_path)
        self._photo_queue.put(photo_info)
        self._photos.append(photo_info)
        return len(self._photos) - 1
