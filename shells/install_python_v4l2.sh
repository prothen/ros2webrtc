#!/bin/bash
git clone https://github.com/iwuvjhdva/v4l2.git
cd v4l2 && python setup.py install
cd ../ && rm -drf v4l2
