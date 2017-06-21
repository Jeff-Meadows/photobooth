# coding: utf-8

from __future__ import unicode_literals
from contextlib import contextmanager
from ctypes import c_int, c_uint, c_char, c_char_p, pointer, POINTER, byref, Structure, sizeof, c_void_p
import os
import select
import sys
import subprocess
from threading import Thread
from time import sleep
from uuid import uuid4

if sys.platform == 'darwin':
    from ctypes import cdll as dll, CFUNCTYPE as functype
else:
    from ctypes import windll as dll, WINFUNCTYPE as functype


class ComThread(Thread):
    def __init__(self, target=None, **kwargs):
        def _start():
            if sys.platform == 'win32':
                import pythoncom
                pythoncom.CoInitialize()
                target()

        super(ComThread, self).__init__(target=_start, **kwargs)


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


class BaseCamera(object):
    def __init__(self, photo_queue):
        self._photo_queue = photo_queue


class EdsCamera(BaseCamera):
    OBJECT_EVENT_ALL = 0x200
    PROP_SAVE_TO = 0xb
    PROP_VAL_SAVE_TO_PC = 0x2
    PROP_VAL_SAVE_TO_CAMERA = 0x1
    DIR_ITEM_CONTEXT_CHANGED = 0x00000208
    PROP_EVENT_ALL = 0x100
    PROP_EVENT_PROP_CHANGED = 0x101
    PROP_EVF_OUTPUT_DEVICE = 0x500
    PROP_EVF_MODE = 0x501
    PROP_EVF_AF_MODE = 0x50e
    COMMAND_PRESS_SHUTTER_BUTTON = 0x4
    PROP_SHUTTER_BUTTON_OFF = 0x0
    PROP_SHUTTER_BUTTON_COMPLETELY = 0x3
    PROP_SHUTTER_BUTTON_HALFWAY = 0x1
    COMMAND_EXTEND_SHUTDOWN = 0x1
    STATUS_COMMAND_UI_LOCK = 0x0
    STATUS_COMMAND_UI_UNLOCK = 0x1

    def __init__(self, photo_queue):
        super(EdsCamera, self).__init__(photo_queue)
        self._create_sdk()
        self._camera = None
        self._waiting_for_callback = False
        self._event_object = None
        self._no_shutdown_thread = None
        self._stop_no_shutdown_thread = False

    def _create_sdk(self):
        if sys.platform == 'darwin':
            library_path = ('edsdk', 'EDSDK.Framework', 'Versions', 'A', 'EDSDK')
        else:
            library_path = ('Windows', 'EDSDK', 'Dll', 'EDSDK.dll')
        self._sdk = dll.LoadLibrary(os.path.join(os.getcwd(), *library_path))

    @contextmanager
    def _initialized_sdk(self):
        initialize_error = self._sdk.EdsInitializeSDK()
        print 'initialize', initialize_error
        if initialize_error:
            raise RuntimeError('Could not inititalize SDK.')
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
        self._no_shutdown_thread = ComThread(target=self._extend_shutdown)
        self._no_shutdown_thread.daemon = True
        self._no_shutdown_thread.start()
        ui_lock_error = self._sdk.EdsSendStatusCommand(self._camera, self.STATUS_COMMAND_UI_LOCK, 0)
        print 'lock ui', ui_lock_error
        save_to_pc = c_int(self.PROP_VAL_SAVE_TO_PC)
        save_to_pc_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_SAVE_TO, 0, sizeof(save_to_pc), byref(save_to_pc))
        print 'set save to pc', save_to_pc_error
        capacity_error = self._sdk.EdsSetCapacity(self._camera, EdsCapacity(0x7fffffff, 0x1000, 1))
        print 'set capacity', capacity_error
        try:
            yield self._camera
        finally:
            save_to_camera = c_int(self.PROP_VAL_SAVE_TO_CAMERA)
            save_to_camera_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_SAVE_TO, 0, sizeof(save_to_camera), byref(save_to_camera))
            print 'set save to camera', save_to_camera_error
            ui_unlock_error = self._sdk.EdsSendStatusCommand(self._camera, self.STATUS_COMMAND_UI_LOCK, 0)
            print 'unlock ui', ui_unlock_error
            close_session_error = self._sdk.EdsCloseSession(self._camera)
            print 'close session', close_session_error
            self._camera = None
            self._stop_no_shutdown_thread = True
            self._no_shutdown_thread = None

    def _extend_shutdown(self):
        while not self._stop_no_shutdown_thread:
            sleep(60)
            try:
                print 'suspend shutdown', self._sdk.EdsSendCommand(self._camera, self.COMMAND_EXTEND_SHUTDOWN, 0)
            except:
                pass

    @contextmanager
    def live_view(self):
        size = sizeof(c_int)
        evf_on_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_EVF_MODE, 1, size, pointer(c_int(1)))
        print 'evf on', evf_on_error  # Turn on EVF
        evf_pc_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_EVF_OUTPUT_DEVICE, 2, size, pointer(c_int(2)))
        print 'evf pc', evf_pc_error  # Set EVF device to PC
        af_live_face_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_EVF_AF_MODE, 1, size, pointer(c_int(2)))
        print 'evf af live face', af_live_face_error  # Set AF Mode to live
        yield
        evf_tft_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_EVF_OUTPUT_DEVICE, 1, size, pointer(c_int(1)))
        print 'evf tft', evf_tft_error  # Set EVF device to TFT
        evf_off_error = self._sdk.EdsSetPropertyData(self._camera, self.PROP_EVF_MODE, 0, size, pointer(c_int(0)))
        print 'evf off', evf_off_error  # Turn off EVF

    def shoot(self):
        shutter_down_error = 1
        while shutter_down_error:
            shutter_half_down_error = self._sdk.EdsSendCommand(self._camera, self.COMMAND_PRESS_SHUTTER_BUTTON, self.PROP_SHUTTER_BUTTON_HALFWAY)
            print 'shutter half down', shutter_half_down_error  # Press shutter button halfway
            shutter_down_error = self._sdk.EdsSendCommand(self._camera, self.COMMAND_PRESS_SHUTTER_BUTTON, self.PROP_SHUTTER_BUTTON_COMPLETELY)
            print 'shutter down', shutter_down_error  # Press shutter button completely
        shutter_up_error = 1
        while shutter_up_error:
            shutter_up_error = self._sdk.EdsSendCommand(self._camera, self.COMMAND_PRESS_SHUTTER_BUTTON, self.PROP_SHUTTER_BUTTON_OFF)
            print 'shutter up', shutter_up_error  # Press shutter button off
        self._waiting_for_callback = True
        while self._waiting_for_callback:
            print 'get event', self._sdk.EdsGetEvent()
            sleep(.2)
        dir_info = EdsDirectoryItemInfo()
        get_directory_item_info_error = self._sdk.EdsGetDirectoryItemInfo(self._event_object, pointer(dir_info))
        print 'get dir info', get_directory_item_info_error
        stream = c_int()
        filename = uuid4().hex + dir_info.szFileName
        print filename
        sys_path = os.path.abspath(os.path.join('image', filename))
        print sys_path
        sys_path_p = c_char_p()
        sys_path_p.value = sys_path
        file_stream_error = self._sdk.EdsCreateFileStream(sys_path_p, 1, 2, byref(stream))
        print 'create file stream', file_stream_error
        download_error = self._sdk.EdsDownload(self._event_object, dir_info.Size, stream)
        print 'download', download_error
        download_complete_error = self._sdk.EdsDownloadComplete(self._event_object)
        print 'dl complete', download_complete_error
        release_error = self._sdk.EdsRelease(self._event_object)
        print 'release dir info', release_error
        self._event_object = None
        release_error = self._sdk.EdsRelease(stream)
        print 'release stream', release_error
        self._photo_queue.put(sys_path)

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
                object_callback_type = functype(c_uint, c_uint, POINTER(c_int), POINTER(c_int))
                object_callback = object_callback_type(object_callback)
                object_error = self._sdk.EdsSetObjectEventHandler(camera, self.OBJECT_EVENT_ALL, object_callback, None)
                print 'set object handler', object_error
                property_callback_type = functype(c_uint, c_uint, c_uint, c_uint, POINTER(c_int))
                property_callback = property_callback_type(property_callback)
                with self.live_view():
                    yield


if __name__ == '__main__':
    from Queue import Queue
    photo_queue, print_queue = Queue(), Queue()
    camera = EdsCamera(photo_queue)
    with camera.run():
        raw_input('Press Space to Shoot')
        camera.shoot()
        print photo_queue.get()
