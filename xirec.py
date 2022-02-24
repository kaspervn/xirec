import argparse
import json
import time
from ctypes import sizeof
from functools import partial
from itertools import starmap
from os import makedirs
from os.path import join

import imageio
from ximea import xiapi

from recorder import *
from utilities import *


def parse_camera_arg(s):
    parts = s.split(':')
    if len(parts) > 2:
        raise ValueError()
    parts[0] = int(parts[0])
    return parts


def camera_from_args(arg) -> xiapi.Camera:
    c = open_camera_by_sn(arg[0])
    if len(arg) > 1:
        apply_camtool_parameters(c, arg[1])
    return c


def save_camera_parameters(parameters, data_dir: str):
    with open(join(data_dir, 'camera_parameters.json'), 'w') as file:
        json.dump(parameters, file, indent=1)


def save_recording(buf: RecordingBuffers, data_dir: str, file_format='tiff'):
    frames_dir = join(data_dir, 'frames')
    makedirs(frames_dir, exist_ok=True)

    with open(join(data_dir, 'frames_metadata.json'), 'w') as file:
        json.dump([frame_metadata_as_dict(frame) for frame in buf.meta_buffer], file, indent=1)

    # make a string format with the right amount of leading 0's
    path_format = f'{{:0{len(str(len(buf.meta_buffer)))}}}'

    for n, (img, video_buf) in enumerate(zip(buf.meta_buffer, buf.video_buffer)):
        img.bp = ctypes.addressof(video_buf)
        img_np = img.get_image_data_numpy()

        imageio.imwrite(join(frames_dir, path_format.format(n) + f'.{file_format}'), img_np)


argparser = argparse.ArgumentParser()

argparser.add_argument('camera-sn:parameter-file', nargs='+', type=parse_camera_arg, help='The parameter file as saved by XiCamtool is optional')
argparser.add_argument('-fc', '--frame_count', default=0, type=int)
argparser.add_argument('-f', '--format', default='tiff', choices=['tiff', 'bmp', 'jpg', 'png'])
argparser.add_argument('-w', '--wait', default='no', help='Wait with recording until the trigger input of specified camera goes high')
argparser.add_argument('--wait-gpi', default=1, choices=list(range(1,13)), help='In case of waiting, selects which GPI port to use as the trigger. Defaults to 1')

args = argparser.parse_args()

no_frames = args.frame_count
saving_format = args.format

print('opening cameras')
cameras = [camera_from_args(arg) for arg in getattr(args, 'camera-sn:parameter-file')]
cameras_sn_str = [cam.get_device_sn().decode() for cam in cameras]

camera_buffers = list(map(partial(allocate_recording_buffers, no_frames=no_frames), map(probe_memory_requirements, cameras)))
print(f'allocated {sum(sizeof(b.video_buffer) for b in camera_buffers) / 1024**3:.2f} gigabyte for video')

print('storing all camera parameters')
cameras_parameter_dump = [get_all_camera_parameters(cam) for cam in cameras]

if args.wait != 'no':
    try:
        cam_to_wait_for_idx = cameras_sn_str.index(args.wait)
    except ValueError:
        print(f'Can not wait for camera with serial number {args.wait} because it is not opened for recording')

    cam_to_wait_for = cameras[cam_to_wait_for_idx]

    selected_gpi = f'XI_GPI_PORT{args.wait_gpi}'

    print(f'Waiting on GPI {args.wait_gpi} of camera {args.wait}')
    while True:
        cam_to_wait_for.set_gpi_selector(selected_gpi)
        if cam_to_wait_for.get_gpi_level():
            break
        time.sleep(0.1)


print('recording')
recording_datetime = datetime.now()
record_cameras(cameras, camera_buffers, no_frames)

print('saving')
recording_dirs = [join(f'{recording_datetime.isoformat().replace(":", "_")}', f'{sn}') for sn in cameras_sn_str]

list(map(makedirs, recording_dirs))

list(starmap(partial(save_recording, file_format=saving_format), zip(camera_buffers, recording_dirs)))

print('analyzing skipped frames')
skipped_frames = list(map(detect_skipped_frames, camera_buffers))
if sum(skipped_frames) > 0:
    for count, camera_sn in zip(skipped_frames, cameras_sn_str):
        print(f'\t[{camera_sn}]: skipped frames: {count}')
else:
    print('\tno skipped frames')

list(map(xiapi.Camera.close_device, cameras))

print('done')
