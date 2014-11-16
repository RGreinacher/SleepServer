#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-
# Read the description.md for a basic understanding of the server API.

from threading import Thread, Event, Timer
from queue import Queue
from daemonize import Daemonize
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import pprint
from systemControl import SystemControl


class IssetHelper:
    def isset(self, dictionary, key):
        try:
            dictionary[key]
        except (NameError, KeyError) as e:
            return False
        else:
            return True

    def isInt(self, integerValue):
        try:
            int(integerValue)
        except (ValueError, TypeError) as e:
            return False
        else:
            return True

    def isFloat(self, floatingValue):
        try:
            float(floatingValue)
        except (ValueError, TypeError) as e:
            return False
        else:
            return True

    def isValueForIndex(self, array, valueForIndex):
        try:
            array.index(valueForIndex)
        except ValueError:
            return False
        else:
            return True

    # return a positive (and > 0) integer (the one that comes next in the array) or -1
    def getIntAfterToken(self, array, token):
        if (self.isValueForIndex(array, token) and
            self.isInt(array[array.index(token) + 1]) and
            int(array[array.index(token) + 1]) > 0):

            return int(array[array.index(token) + 1])
        return -1

    # return a positive float (the one that comes next in the array) or -1.0
    def getFloatAfterToken(self, array, token):
        if (self.isValueForIndex(array, token) and
            self.isFloat(array[array.index(token) + 1]) and
            float(array[array.index(token) + 1]) >= 0):

            return float(array[array.index(token) + 1])
        return -1.0


class HTTPHandler(BaseHTTPRequestHandler, IssetHelper):
    def setSleepServer(self, networkManager):
        self.networkManager = networkManager

    def do_GET(self):
        resourceElements = self.path.split('/')
        returnDict = {}
        if 'sleepApi' in resourceElements:

            # set requests:
            if 'immediateSleep' in resourceElements:
                returnDict = self.networkManager.sleepServerRequest({'set': 'immediateSleep'})
                self.send_response(202)

            # set sleep time
            elif 'setSleepTime' in resourceElements:
                time = self.getIntAfterToken(resourceElements, 'setSleepTime') # identify sleep time
                if time > 0:
                    returnDict = self.networkManager.sleepServerRequest({'set': 'sleepTimer', 'time': time})
                    self.send_response(202)
                else:
                    if kBeVerbose: print('NetworkManager: error parsing sleep time')
                    returnDict = {'errorMessage': 'bad sleep time value'}
                    self.send_response(400)

            # set silence time
            elif 'setSilenceTime' in resourceElements:
                time = self.getIntAfterToken(resourceElements, 'setSilenceTime') # identify silence time
                if time > 0:
                    returnDict = self.networkManager.sleepServerRequest({'set': 'silenceTimer', 'time': time})
                    self.send_response(202)
                else:
                    if kBeVerbose: print('NetworkManager: error parsing silence time')
                    returnDict = {'errorMessage': 'bad silence time value'}
                    self.send_response(400)

            # set good night time
            elif 'setGoodNightTime' in resourceElements:
                time = self.getIntAfterToken(resourceElements, 'setGoodNightTime') # identify good night time
                if time:
                    returnDict = self.networkManager.sleepServerRequest({'set': 'goodNightTimer', 'time': time})
                    self.send_response(202)
                else:
                    if kBeVerbose: print('NetworkManager: error parsing good night time')
                    returnDict = {'errorMessage': 'bad good night time value'}
                    self.send_response(400)

            # set volume
            elif 'setVolume' in resourceElements:
                volume = self.getFloatAfterToken(resourceElements, 'setVolume') # identify the volume value
                if volume >= 0:
                    returnDict = self.networkManager.sleepServerRequest({'set': 'volume', 'percent': volume})
                    self.send_response(202)
                else:
                    if kBeVerbose: print('NetworkManager: error parsing the volume percentage')
                    returnDict = {'errorMessage': 'bad volume value'}
                    self.send_response(400)

            # unset / reset requests:
            elif 'reset' in resourceElements:
                returnDict = self.networkManager.sleepServerRequest({'unset': 'timer'})
                self.send_response(202)

            # status requests:
            elif 'status' in resourceElements:
                returnDict = self.networkManager.sleepServerRequest({'get': 'status'})
                self.send_response(200)

        # error handling for all other requests:
        if returnDict == {}:
            if kBeVerbose: print('NetworkManager: request with unrecognized arguments')
            returnDict = {'errorMessage': 'wrong address, wrong parameters or no such resource'}
            self.send_response(404)

        # headers and define the response content type
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        message = json.dumps(returnDict, ensure_ascii=False)
        self.wfile.write(bytes(message, 'UTF-8'))
        return



class AsyncNetworkManager(Thread, IssetHelper):
    def __init__(self, queue, serverEvent, event):
        # define members:
        self.communicationQueue = queue
        self.serverEvent = serverEvent
        self.networkEvent = event

        # inital method calls
        Thread.__init__(self)

    def run(self):
        httpHandler = HTTPHandler
        httpHandler.setSleepServer(httpHandler, self)

        try:
            # Create a web server and define the handler to manage the incoming request
            server = HTTPServer(('', HTTPSERVERPORT), httpHandler)
            print('SleepServer is up and running at port:', HTTPSERVERPORT)

            # Wait forever for incoming http requests
            server.serve_forever()

        except KeyboardInterrupt:
            print(' AsyncNetworkManager: received interrupt signal; shutting down the HTTP server')
            server.socket.close()

    def sleepServerRequest(self, message):
        # send status request to sleep server via communication queue
        self.communicationQueue.put(message)
        self.serverEvent.set()

        # wait for answer & process it
        self.networkEvent.wait()
        self.networkEvent.clear()

        communicatedMessage = self.communicationQueue.get()
        if self.isset(communicatedMessage, 'status') or self.isset(communicatedMessage, 'error'):
            return communicatedMessage
        else:
            print('AsyncNetworkManager: can\'t read queued values!')
            pprint.pprint(communicatedMessage)



class SleepServer(Thread, IssetHelper):
    """
    Control object of system sleep.
    Definition of the dictionary used in the communication queue between the sleep server and the network manager:

    {'set': 'immediateSleep'}
    {'set': 'sleepTimer', 'time': [INT]}
    {'set': 'silenceTimer', 'time': [INT]}
    {'set': 'goodNightTimer', 'time': [INT]}
    {'set': 'volume', 'percent': [float]}
    {'unset': 'timer'}
    {'get': 'status'}
    """

    def __init__(self):
        # define members:
        self.communicationQueue = Queue()
        self.checkQueueEvent = Event()
        self.networkQueueEvent = Event()
        self.systemControl = SystemControl(kBeVerbose)

        self.sleepTimeRunning = Event()
        self.silenceTimeRunning = Event()
        self.goodNightTimeRunning = Event()

        self.timeLeft = -1
        self.initialTime = -1
        self.status = kNormalStatus

        # inital method calls
        Thread.__init__(self)
        self.currentVolume = self.systemControl.getVolume()
        self.networkManager = AsyncNetworkManager(self.communicationQueue, self.checkQueueEvent, self.networkQueueEvent)
        self.networkManager.start()

    def run(self):
        self.timerTick()

        while self.checkQueueEvent.wait():
            self.checkQueueEvent.clear()
            communicatedMessage = self.communicationQueue.get()

            # handle set commands
            if self.isset(communicatedMessage, 'set'):
                if communicatedMessage['set'] == 'immediateSleep':
                    if kBeVerbose: print('SleepServer: receiving a immediateSleep command')
                    self.status = 'immediateSleep'
                    self.respondToNetworkThread(self.getStatus())
                    self.sleep()

                # handle sleep timer requests
                elif communicatedMessage['set'] == 'sleepTimer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']) and self.setSleepTime(int(communicatedMessage['time'])):
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setSleepTime command')
                        self.respondToNetworkThread({'error': 'bad sleep time'})

                # handle silence timer requests
                elif communicatedMessage['set'] == 'silenceTimer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']) and self.setSilenceTime(int(communicatedMessage['time'])):
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setSilenceTime command')
                        self.respondToNetworkThread({'error': 'bad sleep time'})

                # handle good night timer requests
                elif communicatedMessage['set'] == 'goodNightTimer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']) and self.setGoodNightTime(int(communicatedMessage['time'])):
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setSleepTime command')
                        self.respondToNetworkThread({'error': 'bad sleep time'})

                 # handle set volume requests
                elif communicatedMessage['set'] == 'volume' and self.isset(communicatedMessage, 'percent'):
                    if self.isFloat(communicatedMessage['percent']):
                        if kBeVerbose: print('SleepServer: receiving a setVolume command with', float(communicatedMessage['percent']), '%')
                        self.volumeControl(float(communicatedMessage['percent']))
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setVolume command')
                        self.respondToNetworkThread({'error': 'bad volume percentage'})

            # handle reset / unset commands
            elif self.isset(communicatedMessage, 'unset'):
                if communicatedMessage['unset'] == 'timer':
                    if kBeVerbose: print('SleepServer: receiving a unset sleepTimer command')
                    if self.sleepTimeRunning.isSet() or self.silenceTimeRunning.isSet() or self.goodNightTimeRunning.isSet():
                        self.resetServer()
                        status = self.getStatus()
                        status['acknowledge'] = 'unsettingTimer'
                    else:
                        self.resetServer()
                        status = self.getStatus()
                    self.respondToNetworkThread(status)

            # handle get status requests
            elif self.isset(communicatedMessage, 'get'):
                if communicatedMessage['get'] == 'status':
                    if kBeVerbose: print('SleepServer: receiving a status request')
                    self.respondToNetworkThread(self.getStatus())

            else:
                if kBeVerbose: print('SleepServer: can\'t read values from the network manager thread!')
                pprint.pprint(communicatedMessage)

    def timerTick(self):
        if self.sleepTimeRunning.isSet() or self.silenceTimeRunning.isSet() or self.goodNightTimeRunning.isSet():

            # good night time handling; sleep timer and volume decreasing
            if self.goodNightTimeRunning.isSet():
                if kBeVerbose: print('good night timer tick:', self.timeLeft)
                if self.timeLeft > 0:
                    self.timeLeft -= 1

                    # start changing the volume after getting below 10 min:
                    if self.initialTime > kGoodNightTimeToStartWithVolumeDecrease and self.timeLeft <= kGoodNightTimeToStartWithVolumeDecrease:
                        self.volumeControl((100 * self.timeLeft) / kGoodNightTimeToStartWithVolumeDecrease)
                    elif self.initialTime <= kGoodNightTimeToStartWithVolumeDecrease:
                        self.volumeControl((100 * self.timeLeft) / self.initialTime)
                else:
                    self.sleep()

            # handle only the sleep time
            elif self.sleepTimeRunning.isSet():
                if kBeVerbose: print('sleep timer tick:', self.timeLeft)
                if self.timeLeft > 0:
                    self.timeLeft -= 1
                else:
                    self.sleep()

            # handle only the volume-down-to-silence-time
            elif self.silenceTimeRunning.isSet():
                if kBeVerbose: print('silence timer tick:', self.timeLeft)
                if self.timeLeft > 0:
                    self.timeLeft -= 1
                    self.volumeControl((100 * self.timeLeft) / self.initialTime)
                else:
                    self.resetServer()

        # keep the timer alive
        Timer(1, self.timerTick).start()

    def setSleepTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: receiving a setSleepTime command with', time, 'seconds')
                self.resetServer()
                self.status = kSleepTimerStatus
                self.timeLeft = time

                self.sleepTimeRunning.set()
                return True
        return False

    def setSilenceTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: receiving a setSilenceTime command with', time, 'seconds')
                self.resetServer()
                self.status = kSilenceTimerStatus
                self.initialTime = self.timeLeft = time

                self.currentVolume = 100
                self.volumeControl(self.currentVolume)

                self.silenceTimeRunning.set()
                return True
        return False

    def setGoodNightTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: receiving a setGoodNightTime command with', time, 'seconds')
                self.resetServer()
                self.status = kGoodNightTimerStatus
                self.initialTime = self.timeLeft = time

                self.currentVolume = 100
                self.volumeControl(self.currentVolume)

                self.goodNightTimeRunning.set()
                return True
        return False

    def resetServer(self, volumeChange = 'change'):
        if kBeVerbose: print('SleepServer: resetting the server')

        # reset events
        self.sleepTimeRunning.clear()
        self.silenceTimeRunning.clear()
        self.goodNightTimeRunning.clear()

        # reset members
        self.timeLeft = -1
        self.initialTime = -1
        self.status = kNormalStatus

    def getStatus(self):
        statusDictionary = {'status': self.status, 'currentVolume': self.currentVolume}
        if self.sleepTimeRunning.isSet() or self.goodNightTimeRunning.isSet():
            statusDictionary['timeToSleep'] = self.timeLeft
        elif self.silenceTimeRunning.isSet():
            statusDictionary['timeToSilence'] = self.timeLeft
        return statusDictionary

    def respondToNetworkThread(self, dictionary):
        self.communicationQueue.put(dictionary)
        self.networkQueueEvent.set()

    def sleep(self):
        self.resetServer()
        self.systemControl.setSleep()

    def volumeControl(self, percent):
        if percent > 100:
                percent = 100
        elif percent < 0:
            percent = 0

        self.currentVolume = percent
        self.systemControl.setVolume(self.currentVolume)



# ************************************************
# non object orientated entry code goes down here:
# ************************************************
# defining constants and globals:
HTTPSERVERPORT = 4444
kGoodNightTimeToStartWithVolumeDecrease = 600 # 10 minutes
kBeVerbose = False
kNormalStatus = 'running'
kSleepTimerStatus = 'goingToSleep'
kSilenceTimerStatus = 'goingToSilence'
kGoodNightTimerStatus = 'goingToSleepAndSilence'

def main():
    serverInstance = SleepServer()
    serverInstance.start()

# check if this code is run as a module or was included into another project
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Backend for receiving time-to-sleep signals.")
    parser.add_argument("-d", "--daemon", action = "store_true", dest = "daemon", help = "enables daemon mode")
    parser.add_argument("-v", "--verbose", action = "store_true", dest = "verbose", help = "enables verbose mode")
    parser.add_argument("-p", "--port", type=int, help = "specifies the networking port number")
    args = parser.parse_args()

    if args.verbose:
        kBeVerbose = True

    if args.port:
        HTTPSERVERPORT = args.port

    if args.daemon:
        pidFile = "/tmp/sleepServerDaemon.pid"
        daemon = Daemonize(app='SleepServer Daemon', pid=pidFile, action=main)
        daemon.start()
    else:
        main()
