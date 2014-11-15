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



class HTTPHandler(BaseHTTPRequestHandler, IssetHelper):
    def setSleepServer(self, networkManager):
        self.networkManager = networkManager

    def do_GET(self):
        resourceElements = self.path.split('/')
        returnDict = {}
        if 'sleepApi' in resourceElements:

            # set requests:
            if 'immediateSleep' in resourceElements:
                returnDict = self.networkManager.sleepImmediate()
                self.send_response(202)

            # set sleep time
            elif 'setSleepTime' in resourceElements:
                if (self.isValueForIndex(resourceElements, 'setSleepTime') and
                    self.isInt(resourceElements[resourceElements.index('setSleepTime') + 1]) and
                    int(resourceElements[resourceElements.index('setSleepTime') + 1]) > 0):
                    
                    # sleep time identified and correct
                    returnDict = self.networkManager.setSleepTime(int(resourceElements[resourceElements.index('setSleepTime') + 1]))
                    self.send_response(202)

                else:
                    # sleep time not set, not right after the 'setSleepTime' keywork in the request, not an integer or not greater than 0
                    if kBeVerbose: print('NetworkManager: error parsing sleep time')
                    returnDict = {'errorMessage': 'bad sleep time'}
                    self.send_response(400)

            # set silence time
            elif 'setSilenceTime' in resourceElements:
                if (self.isValueForIndex(resourceElements, 'setSilenceTime') and
                    self.isInt(resourceElements[resourceElements.index('setSilenceTime') + 1]) and
                    int(resourceElements[resourceElements.index('setSilenceTime') + 1]) > 0):
                    
                    # silence time identified and correct
                    returnDict = self.networkManager.setSilenceTime(int(resourceElements[resourceElements.index('setSilenceTime') + 1]))
                    self.send_response(202)

                else:
                    # silence time not set, not right after the 'setSilenceTime' keywork in the request, not an integer or not greater than 0
                    if kBeVerbose: print('NetworkManager: error parsing silence time')
                    returnDict = {'errorMessage': 'bad silence time'}
                    self.send_response(400)

            # set good night time
            elif 'setGoodNightTime' in resourceElements:
                if (self.isValueForIndex(resourceElements, 'setGoodNightTime') and
                    self.isInt(resourceElements[resourceElements.index('setGoodNightTime') + 1]) and
                    int(resourceElements[resourceElements.index('setGoodNightTime') + 1]) > 0):
                    
                    # good night time identified and correct
                    returnDict = self.networkManager.setGoodNightTime(float(resourceElements[resourceElements.index('setGoodNightTime') + 1]))
                    self.send_response(202)

                else:
                    # good night time not set, not right after the 'setGoodNightTime' keywork in the request, not an integer or not greater than 0
                    if kBeVerbose: print('NetworkManager: error parsing good night time')
                    returnDict = {'errorMessage': 'bad good night time'}
                    self.send_response(400)

            # set volume
            elif 'setVolume' in resourceElements:
                if (self.isValueForIndex(resourceElements, 'setVolume') and
                    self.isFloat(resourceElements[resourceElements.index('setVolume') + 1]) and
                    float(resourceElements[resourceElements.index('setVolume') + 1]) >= 0):
                    
                    # good night time identified and correct
                    returnDict = self.networkManager.setVolume(float(resourceElements[resourceElements.index('setVolume') + 1]))
                    self.send_response(202)

                else:
                    # good night time not set, not right after the 'setVolume' keywork in the request, not an integer or not greater than 0
                    if kBeVerbose: print('NetworkManager: error parsing the volume percentage')
                    returnDict = {'errorMessage': 'bad volume percentage'}
                    self.send_response(400)

            # unset / reset requests:
            elif 'reset' in resourceElements:
                returnDict = self.networkManager.unsetTimer()
                self.send_response(202)

            # status requests:
            elif 'status' in resourceElements:
                returnDict = self.networkManager.getStatus()
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

    def sleepImmediate(self):
        return self.sleepServerRequest({'set': 'immediateSleep'})

    def setSleepTime(self, time):
        return self.sleepServerRequest({'set': 'sleepTimer', 'time': time})

    def setSilenceTime(self, time):
        return self.sleepServerRequest({'set': 'silenceTimer', 'time': time})

    def setGoodNightTime(self, time):
        return self.sleepServerRequest({'set': 'goodNightTimer', 'time': time})

    def setVolume(self, percent):
        return self.sleepServerRequest({'set': 'volume', 'percent': percent})

    def unsetTimer(self):
        return self.sleepServerRequest({'unset': 'timer'})

    def getStatus(self):
        return self.sleepServerRequest({'get': 'status'})



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

        self.timerRunning = Event()
        self.sleepTimeRunning = Event()
        self.silenceTimeRunning = Event()
        self.goodNightTimeRunning = Event()

        self.timeToSleep = -1
        self.timeToSilence = -1
        self.timeToGoodNight = -1
        self.initialGoodNightTime = -1
        self.initialSileneTime = -1
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
                    if self.isInt(communicatedMessage['time']):
                        if kBeVerbose: print('SleepServer: receiving a setSleepTime command with', int(communicatedMessage['time']), 'seconds')
                        self.resetServer()
                        self.status = kSleepTimerStatus
                        self.timeToSleep = int(communicatedMessage['time'])

                        self.sleepTimeRunning.set()
                        self.timerRunning.set()
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setSleepTime command')
                        self.respondToNetworkThread({'error': 'bad sleep time'})

                # handle silence timer requests
                elif communicatedMessage['set'] == 'silenceTimer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']):
                        if kBeVerbose: print('SleepServer: receiving a setSilenceTime command with', int(communicatedMessage['time']), 'seconds')
                        self.resetServer()
                        self.status = kSilenceTimerStatus
                        self.timeToSilence = int(communicatedMessage['time'])
                        self.initialSileneTime = self.timeToSilence

                        self.currentVolume = 100
                        self.volumeControl(self.currentVolume)

                        self.silenceTimeRunning.set()
                        self.timerRunning.set()
                        self.respondToNetworkThread(self.getStatus())
                    else:
                        if kBeVerbose: print('SleepServer: error parsing the received setSilenceTime command')
                        self.respondToNetworkThread({'error': 'bad sleep time'})

                # handle good night timer requests
                elif communicatedMessage['set'] == 'goodNightTimer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']):
                        if kBeVerbose: print('SleepServer: receiving a setGoodNightTime command with', int(communicatedMessage['time']), 'seconds')
                        self.resetServer()
                        self.status = kGoodNightTimerStatus
                        self.timeToGoodNight = int(communicatedMessage['time'])
                        self.initialGoodNightTime = self.timeToGoodNight

                        self.goodNightTimeRunning.set()
                        self.timerRunning.set()
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
                    if self.timerRunning.isSet():
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
        if self.timerRunning.isSet():

            # good night time handling; sleep timer and volume decreasing
            if self.goodNightTimeRunning.isSet():
                if kBeVerbose: print('good night timer tick:', self.timeToGoodNight)
                if self.timeToGoodNight > 0:
                    self.timeToGoodNight -= 1

                    # start changing the volume after getting below 10 min:
                    if self.initialGoodNightTime > kGoodNightTimeToStartWithVolumeDecrease and self.timeToGoodNight <= kGoodNightTimeToStartWithVolumeDecrease:
                        self.volumeControl((100 * self.timeToGoodNight) / kGoodNightTimeToStartWithVolumeDecrease)
                    elif self.initialGoodNightTime <= kGoodNightTimeToStartWithVolumeDecrease:
                        self.volumeControl((100 * self.timeToGoodNight) / self.initialGoodNightTime)
                else:
                    self.sleep()

            # handle only the sleep time
            elif self.sleepTimeRunning.isSet():
                if kBeVerbose: print('sleep timer tick:', self.timeToSleep)
                if self.timeToSleep > 0:
                    self.timeToSleep -= 1
                else:
                    self.sleep()

            # handle only the volume-down-to-silence-time
            elif self.silenceTimeRunning.isSet():
                if kBeVerbose: print('silence timer tick:', self.timeToSilence)
                if self.timeToSilence > 0:
                    self.timeToSilence -= 1
                    self.volumeControl((100 * self.timeToSilence) / self.initialSileneTime)
                else:
                    self.resetServer()

        # keep the timer alive
        Timer(1, self.timerTick).start()

    def setSleepTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: set sleep time to', time)
                self.status = kSleepTimerStatus
                self.timeToSleep = time
                self.sleepTimeRunning.set()
                self.timerRunning.set()
                return True
        return False

    def setSilenceTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: set silence time to', time)
                self.status = kSilenceTimerStatus
                self.timeToSilence = time

                self.currentVolume = 100
                self.volumeControl(self.currentVolume)

                self.silenceTimeRunning.set()
                self.timerRunning.set()
                return True
        return False

    def setGoodNightTime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                if kBeVerbose: print('SleepServer: set good night time to', time)
                self.status = kGoodNightTimerStatus
                self.timeToGoodNight = time

                self.currentVolume = 100
                self.volumeControl(self.currentVolume)

                self.goodNightTimeRunning.set()
                self.timerRunning.set()
                return True
        return False

    def resetServer(self, volumeChange = 'change'):
        if kBeVerbose: print('SleepServer: resetting the server')

        # reset events
        self.timerRunning.clear()
        self.sleepTimeRunning.clear()
        self.silenceTimeRunning.clear()
        self.goodNightTimeRunning.clear()

        # reset members
        self.timeToSleep = -1
        self.timeToSilence = -1
        self.timeToGoodNight = -1
        self.initialGoodNightTime = -1
        self.initialSileneTime = -1
        self.status = kNormalStatus

    def getStatus(self):
        statusDictionary = {'status': self.status, 'currentVolume': self.currentVolume}
        if self.sleepTimeRunning.isSet():
            statusDictionary['timeToSleep'] = self.timeToSleep
        if self.goodNightTimeRunning.isSet():
            statusDictionary['timeToSleep'] = self.timeToGoodNight
        elif self.silenceTimeRunning.isSet():
            statusDictionary['timeToSilence'] = self.timeToSilence

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
