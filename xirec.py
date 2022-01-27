import ctypes
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import imageio
from dataclasses import dataclass
from ximea import xiapi


def frame_metadata_as_dict(img):
    def ctypes_convert(obj):  # Very crippled implementation, that is good enough to convert XI_IMG structs.
        if isinstance(obj, (bool, int, float, str)):
            return obj

        if isinstance(obj, ctypes.Array):
            return [ctypes_convert(e) for e in obj]

        if obj is None:
            return obj

        if isinstance(obj, ctypes.Structure):
            result = {}
            anonymous = getattr(obj, '_anonymous_', [])

            for key, *_ in getattr(obj, '_fields_', []):
                value = getattr(obj, key)

                if key.startswith('_'):
                    continue

                if key in anonymous:
                    result.update(ctypes_convert(value))
                else:
                    result[key] = ctypes_convert(value)

            return result

    result = ctypes_convert(img)
    for key in ['bp', 'size', 'bp_size']:
        del result[key]
    return result


def apply_camtool_parameters(cam: xiapi.Camera, xicamera_file_path):
    tree = ET.parse(xicamera_file_path)
    root = tree.getroot()

    type_map = {
        'int': int,
        'float': float,
        'bool': int,
        'string': str,
    }

    if cam.get_device_sn().decode() != root.attrib['serial']:
        print('warning: applying camera setting file from different camera than it is being applied to')

    for par_xml in root.find('Values'):
        parameter_key = par_xml.tag
        parameter_type = par_xml.attrib['type']

        if par_xml.text is not None:
            parameter_value = type_map[parameter_type](par_xml.text)

            # Convert enumerator values to their matching string expected by Camera.set_param
            xiapi_type = xiapi.VAL_TYPE[parameter_key.split(':')[0]]
            if xiapi_type == 'xiTypeEnum':
                parameter_value = next(
                    key for key, val in xiapi.ASSOC_ENUM[parameter_key].items() if parameter_value == val.value)
            if xiapi_type == 'xiTypeInteger' and isinstance(parameter_value, (int, float)):
                parameter_value = int(parameter_value)

            if cam.get_param(parameter_key) != parameter_value:
                try:
                    cam.set_param(parameter_key, parameter_value)
                except xiapi.Xi_error as e:
                    print(f'warning: could not set {parameter_key} to {parameter_value}: {e.descr}')

# cam_snos = [23152050, 23150750]
cam_snos = [23150750]
record_no_frames = 4

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

    apply_camtool_parameters(cam, 'test_cf_mono8_roi_400ms.xicamera')

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
recording_datetime = datetime.now()
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
            print(f'[{cam_n}] skipped frames detected: {a} -> {b}')

recording_dir = lambda n: os.path.join(f'{recording_datetime.isoformat().replace(":", "_")}', f'{cam_snos[n]}')

for cam_n, record_data in enumerate(recording_data):
    data_dir = recording_dir(cam_n)
    frames_dir = os.path.join(data_dir, 'frames')

    os.makedirs(data_dir, exist_ok=False)
    os.makedirs(frames_dir, exist_ok=True)

    with open(os.path.join(data_dir, 'metadata.json'), 'w') as f:
        json.dump([frame_metadata_as_dict(img) for img in record_data.frame_info_buffer], f, indent=1)

    for i in range(0, record_no_frames):
        img.bp = ctypes.addressof(record_data.frame_data_buffer) + record_data.frame_size * i
        img_np = img.get_image_data_numpy()
        imageio.imwrite(os.path.join(frames_dir, f'{i:06}.tiff'), img_np)
