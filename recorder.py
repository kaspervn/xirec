from ximea import xiapi
import ctypes
from typing import List
from dataclasses import dataclass
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


def record_cameras(cameras: List[xiapi.Camera], buffers: List[RecordingBuffers], no_frames):
    for cam in cameras:
        cam.start_acquisition()

    img = xiapi.Image()
    for i in range(no_frames):
        for cam_n, cam in enumerate(cameras):
            cam.get_image(img)

            ctypes.memmove(ctypes.addressof(buffers[cam_n].meta_buffer[i]), ctypes.addressof(img), ctypes.sizeof(xiapi.XI_IMG))
            ctypes.memmove(buffers[cam_n].video_buffer[i], img.bp, ctypes.sizeof(buffers[cam_n].video_buffer[i]))

    for cam in cameras:
        cam.stop_acquisition()


def detect_skipped_frames(recording_buffer: RecordingBuffers):
    skip_count = 0
    for i in range(1, len(recording_buffer.meta_buffer)):
        a = recording_buffer.meta_buffer[i].nframe
        b = recording_buffer.meta_buffer[i-1].nframe
        skip_count += a - b - 1
    return skip_count