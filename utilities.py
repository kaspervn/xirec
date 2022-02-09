import ctypes
from xml.etree import ElementTree as ET

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
    sn_str = cam.get_device_sn().decode()

    type_map = {
        'int': int,
        'float': float,
        'bool': int,
        'string': str,
    }

    if cam.get_device_sn().decode() != root.attrib['serial']:
        print(f'[{sn_str}] warning: applying camera setting file from different camera than it is being applied to')

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
                    print(f'[{sn_str}] warning: could not set {parameter_key} to {parameter_value}: {e.descr}')


def get_all_camera_parameters(cam: xiapi.Camera):

    def safe_cam_get(cam, param):
        try:
            val = cam.get_param(param)
            if isinstance(val, bytes):
                val = val.decode()
            return val
        except xiapi.Xi_error as e:
            return None

    return {param: val for param in xiapi.VAL_TYPE.keys() if (val := safe_cam_get(cam, param)) is not None}


def get_frame_counters(cam: xiapi.Camera):
    cam.set_counter_selector('XI_CNT_SEL_API_SKIPPED_FRAMES')
    api_skipped = cam.get_counter_value()
    cam.set_counter_selector('XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES')
    transport_skipped = cam.get_counter_value()
    return api_skipped, transport_skipped


def open_camera_by_sn(sn):
    c = xiapi.Camera()
    c.open_device_by_SN(str(sn))
    return c