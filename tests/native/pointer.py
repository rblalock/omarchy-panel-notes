"""Disposable Linux virtual pointer for native input acceptance, never runtime."""
import fcntl
import os
import struct
import time


class Pointer:
    def __init__(self):
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        for kind in (1, 2): fcntl.ioctl(self.fd, 0x40045564, kind)
        fcntl.ioctl(self.fd, 0x40045565, 272)
        for axis in (0, 1): fcntl.ioctl(self.fd, 0x40045566, axis)
        setup = struct.pack('80sHHHHI', b'Panel Notes acceptance pointer', 3, 1, 1, 1, 0) + bytes(1024)
        os.write(self.fd, setup)
        fcntl.ioctl(self.fd, 0x5501)
        time.sleep(.3)

    def click(self):
        for value in (1, 0):
            os.write(self.fd, struct.pack('llHHi', 0, 0, 1, 272, value))
            os.write(self.fd, struct.pack('llHHi', 0, 0, 0, 0, 0))
            time.sleep(.06)

    def close(self):
        fcntl.ioctl(self.fd, 0x5502)
        os.close(self.fd)


class Keyboard(Pointer):
    def __init__(self):
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, 0x40045564, 1)
        for key in (125, 56, 49): fcntl.ioctl(self.fd, 0x40045565, key)
        os.write(self.fd, struct.pack('80sHHHHI', b'Panel Notes acceptance keyboard', 3, 1, 2, 1, 0) + bytes(1024))
        fcntl.ioctl(self.fd, 0x5501); time.sleep(.3)

    def shortcut(self):
        for value, keys in ((1, (125,56,49)), (0, (49,56,125))):
            for key in keys:
                os.write(self.fd, struct.pack('llHHi',0,0,1,key,value))
                os.write(self.fd, struct.pack('llHHi',0,0,0,0,0))
                time.sleep(.04)
