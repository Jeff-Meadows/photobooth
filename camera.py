# coding: utf-8

from __future__ import unicode_literals
from contextlib import contextmanager
from ctypes import c_int, c_uint, c_char, c_char_p, pointer, POINTER, byref, Structure, sizeof
from ctypes import windll, WINFUNCTYPE
import os
from Queue import Queue
import subprocess
from threading import Thread
from time import sleep
from uuid import uuid4
from box import Box


class EdsDirectoryItemInfo(Structure):
    _fields_ = [
        ('Size', c_uint),
        ('isFolder', c_int),
        ('GroupID', c_uint),
        ('Option', c_uint),
        ('szFileName', c_char * 256),
        ('format', c_uint),
        ('dateTime', c_uint),
    ]


class EdsCapacity(Structure):
    _fields_ = [
        ('NumberOfFreeClusters', c_int),
        ('BytesPerSector', c_int),
        ('Reset', c_int),
    ]


class Camera(object):
    OBJECT_EVENT_ALL = 0x200
    PROP_SAVE_TO = 0xb
    PROP_VAL_SAVE_TO_PC = 2
    DIR_ITEM_CONTEXT_CHANGED = 0x00000208
    PROP_EVENT_ALL = 0x100
    PROP_EVENT_PROP_CHANGED = 0x101
    PROP_EVF_MODE = 0x501

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
        self._waiting_for_callback = False
        self._event_object = None

    def _create_sdk(self):
        self._sdk = windll.LoadLibrary(os.path.join(os.getcwd(), 'Windows', 'EDSDK', 'Dll', 'EDSDK.dll'))

    def _process_queue(self):
        while True:
            self._box.upload_photo(*self._photo_queue.get())

    @contextmanager
    def _initialized_sdk(self):
        print 'initialize', self._sdk.EdsInitializeSDK()
        try:
            yield
        finally:
            print 'terminate', self._sdk.EdsTerminateSDK()

    @contextmanager
    def _camera_session(self):
        camera_list_ref = c_int()
        camera_list_error = self._sdk.EdsGetCameraList(byref(camera_list_ref))
        print 'get list', camera_list_error
        self._camera = c_int()
        camera_error = self._sdk.EdsGetChildAtIndex(camera_list_ref, 0, byref(self._camera))
        print 'get camera', camera_error
        print self._camera
        session_error = self._sdk.EdsOpenSession(self._camera)
        print 'open session', session_error
        try:
            yield self._camera
        finally:
            close_session_error = self._sdk.EdsCloseSession(self._camera)
            print 'close session', close_session_error
            self._camera = None

    @contextmanager
    def live_view(self):
        #EdsCreateEvfImageRef, EdsDownloadEvfImage, kEdsCameraCommand_DoEvfAf
        size = sizeof(c_int)
        evf_on_error = self._sdk.EdsSetPropertyData(self._camera, 0x00000501, 0, size, pointer(c_int(1)))
        print evf_on_error  # Turn on EVF
        evf_pc_error = self._sdk.EdsSetPropertyData(self._camera, 0x00000500, 0, size, pointer(c_int(2)))
        print evf_pc_error  # Set EVF device to PC
        af_live_face_error = self._sdk.EdsSetPropertyData(self._camera, 0x0000050E, 0, size, pointer(c_int(2)))
        print af_live_face_error  # Set AF Mode to live face
        stream = c_int()
        sys_path = os.path.abspath(os.path.join('evf', 'evf.jpg'))
        sys_path_p = c_char_p()
        sys_path_p.value = sys_path
        create_stream_error = self._sdk.EdsCreateFileStream(sys_path_p, 1, 2, byref(stream))
        print 'create stream', create_stream_error
        #self._sdk.EdsCreateMemoryStream(0, byref(memory_stream))
        evf_image = c_int()
        create_image_ref_error = self._sdk.EdsCreateEvfImageRef(stream, byref(evf_image))
        print 'create image ref', create_image_ref_error
        yield evf_image
        release_error = self._sdk.EdsRelease(evf_image)
        print 'release image', release_error
        release_error = self._sdk.EdsRelease(stream)
        print 'release stream', release_error
        evf_tft_error = self._sdk.EdsSetPropertyData(self._camera, 0x00000500, 0, size, pointer(c_int(1)))
        print evf_tft_error  # Set EVF device to TFT
        evf_off_error = self._sdk.EdsSetPropertyData(self._camera, 0x00000501, 0, size, pointer(c_int(0)))
        print evf_off_error  # Turn off EVF

    def get_evf_frame(self, evf_image):
        while True:
            download_evf_image_error = self._sdk.EdsDownloadEvfImage(self._camera, evf_image)
            error = download_evf_image_error
            print 'download image', error
            if not error:
                break
        sys_path = os.path.abspath(os.path.join('evf', 'evf.jpg'))
        return sys_path

    def shoot(self, name, email):
        self._name = name
        self._email = email
        shutter_down_error = self._sdk.EdsSendCommand(self._camera, 0x00000004, 3)
        print 'shutter down', shutter_down_error  # Press shutter button completely
        shutter_up_error = self._sdk.EdsSendCommand(self._camera, 0x00000004, 0)
        print 'shutter up', shutter_up_error  # Press shutter button off
        self._waiting_for_callback = True
        while self._waiting_for_callback:
            print 'get event', self._sdk.EdsGetEvent()
            sleep(.2)
        dir_info = EdsDirectoryItemInfo()
        get_directory_item_info_error = self._sdk.EdsGetDirectoryItemInfo(self._event_object, pointer(dir_info))
        print 'get dir info', get_directory_item_info_error
        stream = c_int()
        self._filename = uuid4().hex + dir_info.szFileName
        print self._filename
        sys_path = os.path.abspath(os.path.join('image', self._filename))
        print sys_path
        sys_path_p = c_char_p()
        sys_path_p.value = sys_path
        file_stream_error = self._sdk.EdsCreateFileStream(sys_path_p, 1, 2, byref(stream))
        print 'create file stream', file_stream_error
        download_error = self._sdk.EdsDownload(self._event_object, dir_info.Size, stream)
        print 'download', download_error
        #sleep(2)
        download_complete_error = self._sdk.EdsDownloadComplete(self._event_object)
        print 'dl complete', download_complete_error
        release_error = self._sdk.EdsRelease(self._event_object)
        print 'release dir info', release_error
        self._event_object = None
        release_error = self._sdk.EdsRelease(stream)
        print 'release stream', release_error
        photo_info = (self._name, self._email, sys_path)
        self._photo_queue.put(photo_info)
        self._photos.append(photo_info)
        return len(self._photos)

    @property
    def filename(self):
        return self._filename

    @property
    def photos(self):
        return self._photos

    @contextmanager
    def run(self):
        def object_callback(event_type, object_ref, _):
            print 'got object callback', event_type, object_ref
            if event_type == self.DIR_ITEM_CONTEXT_CHANGED:
                print 'got dir item context changed callback'
                self._waiting_for_callback = False
                self._event_object = object_ref
            return 0

        def property_callback(event_type, property_id, param, _):
            print 'got property callback', event_type, property_id, param
            if property_id == self.PROP_EVF_MODE:
                self._waiting_for_callback = False

        with self._initialized_sdk():
            with self._camera_session() as camera:
                object_callback_type = WINFUNCTYPE(c_uint, c_uint, POINTER(c_int), POINTER(c_int))
                object_callback = object_callback_type(object_callback)
                object_error = self._sdk.EdsSetObjectEventHandler(camera, self.OBJECT_EVENT_ALL, object_callback, None)
                print 'set object handler', object_error
                property_callback_type = WINFUNCTYPE(c_uint, c_uint, c_uint, c_uint, POINTER(c_int))
                property_callback = property_callback_type(property_callback)
                size = sizeof(c_int)
                save_to_pc_error = self._sdk.EdsSetPropertyData(camera, self.PROP_SAVE_TO, 0, size, pointer(c_int(2)))
                print 'set save to pc', save_to_pc_error
                capacity_error = self._sdk.EdsSetCapacity(camera, EdsCapacity(0x7fffffff, 0x1000, 1))
                print 'set capacity', capacity_error
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


if __name__ == '__main__':
    from datetime import datetime, timedelta
    camera = Camera()
    count = 1
    with camera.run():
        seconds = 5
        stop_time = datetime.now() + timedelta(seconds=seconds)
        with camera.live_view() as view:
            while datetime.now() < stop_time:
                filename = camera.get_evf_frame(view)
                if filename:
                    with open(filename, 'rb') as evf_file:
                        frame = evf_file.read()
                    with open(os.path.join('evf', str(count) + '.jpg'), 'wb') as evf_log:
                        evf_log.write(frame)
                    count += 1
