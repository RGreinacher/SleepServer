#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-

import subprocess
import platform

# defining constants
kUnsupportedPlatform = 'notSupported'
kMacOSX = 'Darwin'

class SystemControl:
    def __init__(self, beVerbose):
        # define members:
        self.beVerbose = beVerbose

        # define OS identification for OS dependent sleep / volume commands:
        if kMacOSX in platform.platform():
            self.currentOSIdentifier = kMacOSX
        else:
            self.currentOSIdentifier = kUnsupportedPlatform

    def setSleep(self):
        if self.beVerbose: print('Sleep now. Good night!')

        if self.currentOSIdentifier == kMacOSX:
            subprocess.call(['osascript', '-e', 'tell application "System Events" to sleep'])
        elif self.currentOSIdentifier == kUnsupportedPlatform:
            print('sleep for this platform not yet implemented!')

    def setShutdown(self):
        if self.beVerbose: print('Shutdown now. Good night!')
        
        if self.currentOSIdentifier == kMacOSX:
            subprocess.call(['osascript', '-e', 'tell application "System Events" to shut down'])
        elif self.currentOSIdentifier == kUnsupportedPlatform:
            print('shutdown for this platform not yet implemented!')

    def setVolume(self, percent):
        if percent > 100:
            if self.beVerbose: print('setting the volume to', str(percent), 'is not possible; cutting it at 100%')
            percent = 100
        elif percent < 0:
            if self.beVerbose: print('setting the volume to', str(percent), 'is not possible; settint it to 0%')
            percent = 0

        if self.currentOSIdentifier == kMacOSX:
            targetVolume = (7 * percent) / 100
            subprocess.call(['osascript', '-e', 'Set volume ' + str(targetVolume)])
        elif self.currentOSIdentifier == kUnsupportedPlatform:
            print('setting the volume for this platform not yet implemented!')

    def getVolume(self):
        if self.currentOSIdentifier == kMacOSX:
            # subprocess.call(['osascript', '-e', 'get volume settings']) # TODO
            return 100
        elif self.currentOSIdentifier == kUnsupportedPlatform:
            print('setting the volume for this platform not yet implemented!')
            return 100