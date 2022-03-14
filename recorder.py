from ximea import xiapi
import ctypes
from typing import List
from dataclasses import dataclass
from threading import Thread
from datetime import datetime

@dataclass
class RecordingBuffers:
    video_buffer: ctypes.Array
    meta_buffer: ctypes.Array


def probe_memory_requirements(cam: xiapi.Camera):
    img = xiapi.Image()
    cam.start_acquisition()
    cam.get_image(img)
    frame_data_size = img.get_bytes_per_pixel() * (img.width + img.padding_x) * img.height
    cam.stop_acquisition()

    return frame_data_size


def allocate_recording_buffers(frame_size, no_frames):
    video_buffer = ((ctypes.c_char * frame_size) * no_frames)()
    meta_buffer = (xiapi.Image * no_frames)()

    return RecordingBuffers(video_buffer, meta_buffer)


def record_camera_thread(cam: xiapi.Camera, buffer: RecordingBuffers, no_frames):
    cam.start_acquisition()

    img = xiapi.Image()
    for i in range(no_frames):
        cam.get_image(img)
        ctypes.memmove(ctypes.addressof(buffer.meta_buffer[i]), ctypes.addressof(img), ctypes.sizeof(xiapi.XI_IMG))
        ctypes.memmove(buffer.video_buffer[i], img.bp, ctypes.sizeof(buffer.video_buffer[i]))

    cam.stop_acquisition()


def record_cameras(cameras: List[xiapi.Camera], buffers: List[RecordingBuffers], no_frames: List[int]):
    threads = [Thread(target=record_camera_thread, name=f'recording thread {n}', args=(cameras[n], buffers[n], no_frames[n])) for n in range(len(cameras))]

    for t in threads:
        t.start()

    for t in threads:
        t.join()


def detect_skipped_frames(recording_buffer: RecordingBuffers):
    skip_count = 0
    for i in range(1, len(recording_buffer.meta_buffer)):
        a = recording_buffer.meta_buffer[i].nframe
        b = recording_buffer.meta_buffer[i-1].nframe
        skip_count += a - b - 1
    return skip_count