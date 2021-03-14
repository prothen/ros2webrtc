# ROS2WebRTC

Simple transition node utilising Video4Linux kernel module to stream ROS1 videos in a WebRTC compliant way in form of mediastreams.

_Note: This package is in a development stage and the setup process has not matured yet. If you encounter problems please reach out by opening an issue. It is very likely that there are barely minor conflicts in the setup process or residual code inconsistencies._

## Usage
Launch the ROS node using
```bash
roslaunch ros2webrtc stream.launch config:=default stream_name:=zed
```

_Note:
The `config/*.yaml` file describes under the namespace `stream` the available streams with their device ID of the kernel module (used in `sudo modprobe v4l2loopback video_nr=1,3,6` where ID is for example any of `(1,3,6)`.
The `stream` argument `roslaunch ros2webrtc stream.launch stream:=zed config:=default` defines the topic and stream. Allows to run multiple devices at the same time.
Verify that you have added all desired IDs to the kernel command before executing the launch command._

You may verify the successful streaming under the [WebRTC sample page here](https://webrtc.github.io/samples/src/content/getusermedia/gum/).

## Setup
1. Install the Python packages with
    - `pip install -r requirements.txt` (Additionally install `opencv-python`)
    - For video4linux2 with Python3 support use the convenience shell script under `resources/python_v42l`
2. Install kernel module for `video4linux2` from [here](https://github.com/umlaeute/v4l2loopback)
    - You may use the convenience shell script under `resources/kernel_module_v4l2.sh` (For kernel installation under secure boot see [here](https://askubuntu.com/questions/760671/could-not-load-vboxdrv-after-upgrade-to-ubuntu-16-04-and-i-want-to-keep-secur/768310#768310) and for instructions for MOK installation see [here](https://sourceware.org/systemtap/wiki/SecureBoot))

## Reference
A great reference for example usage of the Python v4l2 library can also be found [here.](https://github.com/stonecontagion/v4l2-python-example/blob/master/cam.py)


## Contribution
Any contribution is welcome.
If you find missing instructions or something did not work as expected please create an issue and let me know.

## License
See the `LICENSE` file for details of the available open source licensing.
