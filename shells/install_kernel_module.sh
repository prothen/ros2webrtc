#!/bin/bash
#
# Bash script for automatic kernel installation under Secure Boot constraints.
#
#       Note:
#               https://sourceware.org/systemtap/wiki/SecureBoot
#
# Author: Philipp Rothenhäusler, Stockholm 2020
#


# test if kernel module is installed or not
if test -n "$(modinfo v4l2loopback>/dev/null)"; then
        git clone https://github.com/umlaeute/v4l2loopback.git
        cd v4l2loopback
        make && sudo make install
        sudo depmod -a
fi
sudo modprobe v4l2loopback
if test -n "$(grep -e "^v4l2loopback" /proc/modules)"; then
        echo "Successfuly installed kernel module."
        echo "Cleaning up now, but leaving installed keys around just in case..."
        rm -drf v4l2loopback
        exit
else
        echo "Module not installed properly. Follow subsequent instruction for secure boot"
fi

if ! [ -x "$(command -v mokutil)" ]; then
        sudo apt install mokutil
fi

f="$(pwd)/MOK.der"
if ! [[ -f "$f" ]]; then
        echo "MOK.der NOT FOUND -> generate signing key."
        git clone https://github.com/umlaeute/v4l2loopback.git
        cd v4l2loopback
        make && sudo make install
        sudo depmod -a
        sudo modprobe v4l2loopback
        if test -n "$(grep -e "^v4l2loopback" /proc/modules)"; then
                echo "Successfuly installed kernel module."
                exit

                echo "Module not installed properly. Follow subsequent instruction for secure boot"
        fi
        cd ..
        openssl req -new -x509 -newkey rsa:2048 -keyout MOK.priv -outform DER -out MOK.der -nodes -days 36500 -subj "/CN=Descriptive common name/"

        p=$(modinfo -n v4l2loopback)
        sudo /usr/src/linux-headers-$(uname -r)/scripts/sign-file sha256 ./MOK.priv ./MOK.der $(modinfo -n v4l2loopback)
        echo "Is signed?"
        echo "$(tail $(modinfo -n v4l2loopback) | grep 'Module signature appended')"
        sudo mokutil --import MOK.der
        echo "You may reboot now and enroll MOK (Machine Owner Key)"
        echo "Press any key at bluescreen and choose continue, then enter password and reboot."
        echo "You may find illustrations for the GUI steps in this bash script doc string."
        exit
else
        echo "MOK.der FOUND -> skip signing key generation."
        echo "Testing if key is enrolled and modprobe..."
fi
echo "Is signing key installed successfully in enrolled MOK list?"
echo -e "\t-->$(mokutil --test-key MOK.der)"
echo "Install kernel module now..."
sudo modprobe v4l2loopback
echo "$ret"
echo "Done!"
echo "Cleaning up now, but leaving installed keys around just in case..."
rm -drf v4l2loopback

# Alternatively
# sudo apt install mokutil
# mokutil --sb-state
# sudo mokutil --disable-validation
# reboot


