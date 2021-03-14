#!/usr/bin/env python2

"""
Generate webrtc media device from ROS based image publisher.

Requires 'sudo modprobe v4l2loopback' (see resources)

Author: Philipp Rothenhaeusler, Stockholm 2020

"""

import os
import sys
import time
import fcntl

import cv2
import v4l2
import numpy
import rospy

from cv_bridge import CvBridge

from sensor_msgs.msg import Image



class Loopback(object):
    """ Defines the convenience wrapper for video4linux device instantiations. """
    def __init__(self, name, debug_is_enabled=True):
        self._debug_is_enabled = debug_is_enabled
        self.name = name
        self.config = dict()
        self._fd = None
        self.cap = {
                'video_capture' : v4l2.V4L2_CAP_VIDEO_CAPTURE,
                'read_write' : v4l2.V4L2_CAP_READWRITE,
                'stream' : v4l2.V4L2_CAP_STREAMING
        }

    def _verify_setup(self, ID):
        """ Test if loaded kernel module supports request. """
        # is kernel module loaded
        if not os.path.isdir('/sys/module/v4l2loopback'):
            print("Kernel module not loaded:")
            print("\t'sudo modprobe v4l2loopback video_nr={}'".format(ID))
            print("-> e.g.:  ... video_nr=2,3,4")
            sys.exit(1)
        import subprocess as sp
        t = sp.Popen('cat /sys/module/v4l2loopback/parameters/video_nr'.split(), stdin=sp.PIPE, stdout=sp.PIPE)
        lu = t.stdout.read().decode('utf8').split(',')
        l = [int(li) for li in lu]
        if not ID in l:
            print('Device: {0} not in {1}'.format(ID, l))
            print('-> check modprobe video_nr parameter')
            sys.exit(1)
        return True

    def write(self, bytes):
        """ Parse write command to descriptor. """
        self._fd.write(bytes)

    def can(self, capability):
        """ Return a boolean if capability is satisfied. """
        return bool(self.config['capabilities'] & self.cap[capability])

    def print_format(self, fmt):
        """ Print the format of the device. """
        print('Width :          \t\t {}'.format(fmt.fmt.pix.width))
        print('Height :         \t\t {}'.format(fmt.fmt.pix.height))
        print('Pixelformat:     \t\t {:02X}'.format(fmt.fmt.pix.pixelformat))
        print('  -> v4l2.V4L2_PIX_FMT_YUYV \t {0}'.format(bool(fmt.fmt.pix.pixelformat & v4l2.V4L2_PIX_FMT_YUYV)))
        print('Bytes per line : \t\t {}'.format(fmt.fmt.pix.bytesperline))
        print('Image size:      \t\t{}'.format(fmt.fmt.pix.sizeimage))

    def _get_capabilities(self):
        """ Fetch capabilities and test if suitable for streamining. """
        cp = v4l2.v4l2_capability()
        fcntl.ioctl(self._fd, v4l2.VIDIOC_QUERYCAP, cp)
        self.config.update(capabilities=cp.capabilities)
        self.config.update(name=cp.card)
        self.config.update(driver=cp.driver)
        if True or self._debug_is_enabled:
            print("Driver name  :           \t{}".format(self.config['name']))
            print("Driver capabilities :    \t0x{0:02X}".format(self.config['capabilities']))
            print("Driver capabilities :    \t0x{0:02X}".format(self.config['capabilities']))
            for cap in self.cap.keys():
                print('{0} : \t{1}'.format(cap.ljust(20), self.can(cap)))

    def _get_format(self):
        """ Get current format. """
        fmt = v4l2.v4l2_format()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        fcntl.ioctl(self._fd, v4l2.VIDIOC_G_FMT, fmt)

        print('Received format:')
        self.print_format(fmt)

    def _set_format(self):
        """ Set desired format. """
        width = 1280
        height = 720
        fmt = v4l2.v4l2_format()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT

        fmt.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_YUYV
        fmt.fmt.pix.width = width
        fmt.fmt.pix.height = height
        fmt.fmt.pix.field = v4l2.V4L2_FIELD_NONE
        fmt.fmt.pix.bytesperline = width * 2
        fmt.fmt.pix.sizeimage = width * height * 2
        fcntl.ioctl(self._fd, v4l2.VIDIOC_S_FMT, fmt)

        print('Updated format:')
        self.print_format(fmt)

    def _set_output(self):
        """ Define output stream. """
        raise NotImplementedError

    def configure_stream(self, ID=None):
        """ Configure stream if ID is provided,
            otherwise assume it already is and update.
        """
        if ID is not None:
            self._verify_setup(ID)
            self._fd = open('/dev/video' + str(ID), 'rb+', buffering=0)
        self._get_capabilities()
        self._get_format()
        self._set_format()

NS2S = 1.e-9

class WebRTCROSMediaDevice:
    """ Parser for ROS image streams to loopback device for WebRTC Mediastream.

        Todo:
            - implement automatic assignment of videoX number and modprobe
            - porting to Python3 would allow time_ns usage but opencv does fail
    """

    def __init__(self):

        rospy.init_node(name="media_device", anonymous=False)

        # Fetch desired stream
        stream_name = rospy.get_param('~stream_name', 'zed')
        stream = rospy.get_param('~stream', None)
        # Define video4linux kernel device ID -> must be <= 99
        ID = rospy.get_param('~stream/{}/ID'.format(stream_name), '101')
        # Define source topic
        topic = rospy.get_param('~stream/{}/topic'.format(stream_name), '~failed_input_topic')
        # Define desired output frequency
        frequency = rospy.get_param('~stream/{}/frequency'.format(stream_name), 0)

        # Define some statistics
        self._drop_frames = [self._drop_no_frames if frequency == 0 else self._drop_frames][0]
        self._output_rate = rospy.Rate(max(0.001, frequency)) # not used if freq=0
        self._deadline_next_frame = rospy.Time.now() + self._output_rate.sleep_dur
        self._stamp = rospy.Time.now()

        # Attempt startup (verbosified)
        print('Start WebRTC streamer:')
        print('Stream:      \t {}'.format(stream))
        print('ID:          \t {}'.format(ID))
        print('Topic:       \t {}'.format(topic))
        print('Frequency:   \t {}'.format(frequency))

        self._device = Loopback(stream)
        self._device.configure_stream(ID)

        self._idx = {
                'buffer': {'Y': None, 'U': None, 'V': None},
                'source': {'Y': None, 'U': None, 'V': None}
        }
        self._buffer = None
        self._bridge = CvBridge()
        self._output_topic = topic
        self._sub_image = rospy.Subscriber(self._output_topic, Image,
                                        self._cb_init,
                                        queue_size=1,
                                        tcp_nodelay=True)

    def _drop_no_frames(self):
        """ Drop no frames, always handle callback. """
        return False

    def _drop_frames(self):
        """ Drop frames if frequency of subscriber callbacks exceeds specified frequency. """
        if self._deadline_next_frame < rospy.Time.now():
            self._deadline_next_frame = rospy.Time.now() + self._output_rate.sleep_dur
            return False
        return True

    def _cb_init(self, img_input):
        """ Fetch initialisation parameteres from topic. """
        img_cv = self._bridge.imgmsg_to_cv2(img_input)
        img_rgb = cv2.cvtColor(img_cv, cv2.cv2.COLOR_RGBA2BGR)
        img_yuv = cv2.cvtColor(img_cv, cv2.cv2.COLOR_BGR2YUV)

        height, width, ch = img_cv.shape
        lb = width * height * 2

        img_yuv_rav = img_yuv.ravel()
        l = len(img_yuv_rav)

        self._idx['source']['Y'] = numpy.arange(0, l, 3)
        self._idx['source']['U'] = numpy.arange(1, l, 6)
        self._idx['source']['V'] = numpy.arange(2, l, 6)
        self._idx['buffer']['Y'] = numpy.arange(0, lb, 2)
        self._idx['buffer']['U'] = numpy.arange(1, lb, 4)
        self._idx['buffer']['V'] = numpy.arange(3, lb, 4)

        self._buffer = numpy.zeros(lb, dtype=numpy.uint8)
        self._sub_image.unregister()
        self._sub_image = rospy.Subscriber(self._output_topic, Image,
                                        self._cb_yuyv,
                                        queue_size=1, tcp_nodelay=True)

    def _cb_yuyv(self, img_input):
        """ Convert image to yuyv buffer format. """
        if self._drop_frames():
            return
        img_cv = self._bridge.imgmsg_to_cv2(img_input)
        img_rgb = cv2.cvtColor(img_cv, cv2.cv2.COLOR_RGBA2BGR)
        img_yuv = cv2.cvtColor(img_cv, cv2.cv2.COLOR_BGR2YUV).ravel()

        for key, idxs in self._idx['buffer'].items():
            self._buffer[idxs] = img_yuv[self._idx['source'][key]]
        self._device.write(self._buffer.tostring())

        f = 1.  / ((rospy.Time.now() - self._stamp).to_sec())
        self._stamp = rospy.Time.now()
        print('FPS : \t {0:2.0f} Hz'.format(f))

    def stream(self):
        """ Idle node with active subscription thread to maintain streaming. """
        rospy.spin()


if __name__ == '__main__':
    media_device = WebRTCROSMediaDevice()
    media_device.stream()

