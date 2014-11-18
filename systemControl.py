#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-

import subprocess
import platform
import re

# defining constants
UNSUPPORTED_PLATFORM = 'notSupported'
MAC_OS_X = 'Darwin'
LINUX = 'Linux'

class SystemControl:
    def __init__(self, beVerbose):
        # define members:
        self.beVerbose = beVerbose

        # define OS identification for OS dependent sleep / volume commands:
        if MAC_OS_X in platform.platform():
            self.currentOSIdentifier = MAC_OS_X
        elif LINUX in platform.platform():
            self.currentOSIdentifier = LINUX
        else:
            self.currentOSIdentifier = UNSUPPORTED_PLATFORM

    def setSleep(self):
        if self.beVerbose: print('Sleep now. Good night!')

        if self.currentOSIdentifier == MAC_OS_X:
            subprocess.call(['osascript', '-e', 'tell application "System Events" to sleep'])
        elif self.currentOSIdentifier == LINUX:
            subprocess.call('dbus-send --system --print-reply --dest=org.freedesktop.UPower /org/freedesktop/UPower org.freedesktop.UPower.Suspend', shell = True)
        elif self.currentOSIdentifier == UNSUPPORTED_PLATFORM:
            print('sleep for this platform not yet implemented!')

    def setShutdown(self):
        if self.beVerbose: print('Shutdown now. Good night!')
        
        if self.currentOSIdentifier == MAC_OS_X:
            subprocess.call(['osascript', '-e', 'tell application "System Events" to shut down'])
        elif self.currentOSIdentifier == LINUX:
            subprocess.call('dbus-send --system --print-reply --dest=org.freedesktop.ConsoleKit /org/freedesktop/ConsoleKit/Manager org.freedesktop.ConsoleKit.Manager.Stop', shell = True)
        elif self.currentOSIdentifier == UNSUPPORTED_PLATFORM:
            print('shutdown for this platform not yet implemented!')

    def setVolume(self, percent):
        if percent > 100:
            if self.beVerbose: print('setting the volume to', str(percent), 'is not possible; cutting it at 100%')
            percent = 100
        elif percent < 0:
            if self.beVerbose: print('setting the volume to', str(percent), 'is not possible; settint it to 0%')
            percent = 0

        if self.currentOSIdentifier == MAC_OS_X:
            targetVolume = (7 * percent) / 100
            subprocess.call(['osascript', '-e', 'Set volume ' + str(targetVolume)])
        if self.currentOSIdentifier == LINUX:
            subprocess.call('amixer -D pulse sset Master ' + str(percent) + '%', shell = True)
        elif self.currentOSIdentifier == UNSUPPORTED_PLATFORM:
            print('setting the volume for this platform not yet implemented!')

    def getVolume(self):
        if self.currentOSIdentifier == MAC_OS_X:
            # subprocess.call(['osascript', '-e', 'get volume settings']) # TODO
            return 100
        elif self.currentOSIdentifier == LINUX:
            volume = subprocess.check_output('amixer -D pulse get Master', shell = True)
            volume = re.search('([0-9]+)%', str(volume))
            volume = volume.group(1)
            return int(volume)
        elif self.currentOSIdentifier == UNSUPPORTED_PLATFORM:
            print('setting the volume for this platform not yet implemented!')
            return 100
