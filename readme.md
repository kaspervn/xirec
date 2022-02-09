# xirec

Program to record from USB3 XIMEA camera's

* Records from multiple camera's
* Can configure camera based on `.xicamera` files obtained from the offical recording tool, XiCamTool
* Records for a limited time into RAM, and then saves everything to disk
* Saves all frame metadata, including frame timestamps for example
* Commandline interface
* Saves image sequences


## Usage
Run `python xirec.py --help` for basic documentation.

```
usage: xirec.py [-h] [-fc FRAME_COUNT] [-f {tiff,bmp,jpg,png}]
                camera-sn:parameter-file [camera-sn:parameter-file ...]

positional arguments:
  camera-sn:parameter-file
                        The parameter file as saved by XiCamtool is optional

optional arguments:
  -h, --help            show this help message and exit
  -fc FRAME_COUNT, --frame_count FRAME_COUNT
  -f {tiff,bmp,jpg,png}, --format {tiff,bmp,jpg,png}
```

You have to specify what camera's to record from by their serial number. If you want assign a `.xicamera` file, append `:somefile.xicamera` to the serialnumber

Example: `python xirec.yp -fc 20 --format jpg 23150750:test.xicamera 23152050:test.xicamera`
Records for 20 frames from two camera's. Files are saved in jpg format, and loads specific `.xicamera` files.


## Requirements

* Python version 3.7 or higher
* Python libraries:
  * imageio
  * numpy
* [XIMEA's software package](https://www.ximea.com/support/wiki/apis/XIMEA_Windows_Software_Package), including the python API.

## Limitations
* Curently only records for a set amount of frames, not time. All the camera's should have the same framerate