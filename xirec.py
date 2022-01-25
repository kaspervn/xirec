from ximea import xiapi
from time import sleep
import ctypes
import imageio
from dataclasses import dataclass

cam_snos = [23152050, 23150750]
record_no_frames = 170 * 3

def open_camera_by_sn(sn):
    c = xiapi.Camera()
    c.open_device_by_SN(str(sn))
    return c
cameras = [open_camera_by_sn(sn) for sn in cam_snos]

@dataclass
class camera_record_data:
    frame_size: int
    frame_data_buffer: ctypes.Array
    frame_info_buffer: ctypes.Array

recording_data = []

for cam_n, cam in enumerate(cameras):
    cam.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FRAME_RATE')
    cam.set_imgdataformat('XI_RAW8')

    cam.set_framerate(170)

    # get one frame to determine the frame size
    img = xiapi.Image()
    cam.start_acquisition()
    cam.get_image(img)
    frame_data_size = img.get_bytes_per_pixel() * (img.width + img.padding_x) * img.height
    cam.stop_acquisition()

    print(f'[{cam_n}] frame_size: {frame_data_size / 1024 ** 2} megabyte')
    print(f'[{cam_n}] will allocate {frame_data_size * record_no_frames / 1024 ** 3} gigabyte')
    frame_data_buffer = (ctypes.c_char * frame_data_size * record_no_frames)()
    frame_info_buffer = (xiapi.XI_IMG * record_no_frames)()

    recording_data.append(camera_record_data(frame_data_size, frame_data_buffer, frame_info_buffer))

print('recording')

for cam in cameras:
    cam.start_acquisition()

img = xiapi.Image()
for i in range(record_no_frames):
    for cam_n, cam in enumerate(cameras):
        cam.get_image(img)
        ctypes.memmove(ctypes.addressof(recording_data[cam_n].frame_info_buffer) + ctypes.sizeof(xiapi.XI_IMG) * i, ctypes.addressof(img), ctypes.sizeof(xiapi.XI_IMG))
        ctypes.memmove(ctypes.addressof(recording_data[cam_n].frame_data_buffer) + recording_data[cam_n].frame_size * i, img.bp, recording_data[cam_n].frame_size)

for cam in cameras:
    cam.stop_acquisition()

for cam_n, cam in enumerate(cameras):
    cam.set_counter_selector('XI_CNT_SEL_API_SKIPPED_FRAMES')
    print(f'[{cam_n}] api skipped frames: {cam.get_counter_value()}')
    cam.set_counter_selector('XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES')
    print(f'[{cam_n}] transport skipped frames: {cam.get_counter_value()}')

for cam in cameras:
    cam.close_device()

print('done recording')

for cam_n, record_data in enumerate(recording_data):
    for i in range(1, record_no_frames):
        a = record_data.frame_info_buffer[i].nframe
        b = record_data.frame_info_buffer[i-1].nframe
        if a - 1 != b:
            print(f'[{cam_n}] {a} -> {b}')

        # img.bp = ctypes.addressof(frame_data_buffer) + frame_data_size * i
        # img_np = img.get_image_data_numpy()
        # imageio.imwrite(f'testdata/{i}.jpg', img_np)
