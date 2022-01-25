from ximea import xiapi
from time import sleep
import ctypes
import imageio

cam = xiapi.Camera()

#cam.open_device_by_SN('41305651')

cam.open_device()

cam.set_exposure(1000)

cam.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FRAME_RATE')

cam.set_imgdataformat('XI_RAW8')

print(cam.get_framerate_minimum())
print(cam.get_framerate_maximum())
print(cam.get_framerate_increment())

record_no_frames = 170 * 10

cam.set_framerate(170)

cam.set_buffer_policy('XI_BP_UNSAFE')


img = xiapi.Image()

cam.start_acquisition()
sleep(1)
cam.get_image(img)
frame_data_size = img.get_bytes_per_pixel() * (img.width + img.padding_x) * img.height
frame_info_size = img.size
cam.stop_acquisition()

print(f'frame_size: {frame_data_size/1024**2} megabyte')
print(f'will allocate {frame_data_size*record_no_frames/1024**3} gigabyte')

frame_data_buffer = (ctypes.c_char * frame_data_size * record_no_frames)()
frame_info_buffer = (ctypes.c_char * frame_info_size * record_no_frames)()

print('recording')
cam.start_acquisition()
for i in range(record_no_frames):
    cam.get_image(img)
    ctypes.memmove(ctypes.addressof(frame_info_buffer) + frame_info_size * i, ctypes.addressof(img), frame_info_size)
    ctypes.memmove(ctypes.addressof(frame_data_buffer) + frame_data_size * i, img.bp, frame_data_size)

cam.set_counter_selector('XI_CNT_SEL_API_SKIPPED_FRAMES')
print(f'api skipped frames: {cam.get_counter_value()}')
cam.set_counter_selector('XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES')
print(f'transport skipped frames: {cam.get_counter_value()}')

cam.stop_acquisition()
cam.close_device()

print('done recording. saving buffer')
for i in range(record_no_frames):
    img = xiapi.Image.from_address(ctypes.addressof(frame_info_buffer) + frame_info_size * i)
    img.bp = ctypes.addressof(frame_data_buffer) + frame_data_size * i
    img_np = img.get_image_data_numpy()
    imageio.imwrite(f'testdata/{i}.jpg', img_np)
