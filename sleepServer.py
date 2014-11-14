#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-
# Read the description.md for a basic understanding of the server API.

from threading import Thread, Event, Timer
from queue import Queue
from daemonize import Daemonize
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess
import pprint


class IssetHelper:
    def isset(self, dictionary, key):
        try:
            dictionary[key]
        except (NameError, KeyError) as e:
            return False
        else:
            return True

    def isInt(self, integer):
        try:
            int(integer)
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

            # status requests:
            if 'status' in resourceElements:
                returnDict = self.networkManager.getStatus()
                self.send_response(200)

            # set sleep requests:
            elif 'setSleepTime' in resourceElements:
                if (self.isValueForIndex(resourceElements, 'setSleepTime') and
                    self.isInt(resourceElements[resourceElements.index('setSleepTime') + 1]) and
                    int(resourceElements[resourceElements.index('setSleepTime') + 1]) > 0):
                    
                    # sleep time identified and correct
                    returnDict = self.networkManager.setSleeptime(int(resourceElements[resourceElements.index('setSleepTime') + 1]))
                    self.send_response(202)

                else:
                    # sleep time not set, not right after the 'setSleepTime' keywork in the request, not an integer or not greater than 0
                    returnDict = {'errorMessage': 'bad sleep time'}
                    self.send_response(400)

            elif 'immediateSleep' in resourceElements:
                returnDict = self.networkManager.sleepImmediate()
                self.send_response(202)

            # unset sleep time requests:
            elif 'unsetSleepTime' in resourceElements:
                returnDict = self.networkManager.unsetSleeptime()
                self.send_response(202)

        # error handling for all other requests:
        if returnDict == {}:
            self.send_response(404)
            returnDict = {'errorMessage': 'wrong address, wrong parameters or no such resource'}

        # headers and define the response content type
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        message = json.dumps(returnDict, ensure_ascii=False)
        self.wfile.write(bytes(message, 'UTF-8'))
        return



class AsyncNetworkManager(Thread, IssetHelper):
    def __init__(self, queue, serverEvent, event, port):
        # define members:
        self.communicationQueue = queue
        self.serverEvent = serverEvent
        self.networkEvent = event
        self.serverPort = port

        # inital method calls
        Thread.__init__(self)

    def run(self):
        httpHandler = HTTPHandler
        httpHandler.setSleepServer(httpHandler, self)

        try:
            # Create a web server and define the handler to manage the incoming request
            server = HTTPServer(('', self.serverPort), httpHandler)
            print('SleepServer is up and running at port:', self.serverPort)

            # Wait forever for incoming http requests
            server.serve_forever()

        except KeyboardInterrupt:
            print(' received interrupt signal; shutting down the HTTP server!')
            server.socket.close()

    def sleepServerRequest(self, message):
        # send status request to sleep server via communication queue
        self.communicationQueue.put(message)
        self.serverEvent.set()

        # wait for answer & process it
        self.networkEvent.wait()
        self.networkEvent.clear()

        communicatedMessage = self.communicationQueue.get()
        if self.isset(communicatedMessage, 'status'):
            return communicatedMessage
        else:
            print('AsyncNetworkManager: can\'t read queued values!')
            pprint.pprint(communicatedMessage)

    def sleepImmediate(self):
        return self.sleepServerRequest({'set': 'immediateSleep'})

    def setSleeptime(self, time):
        return self.sleepServerRequest({'set': 'timer', 'time': time})

    def unsetSleeptime(self):
        return self.sleepServerRequest({'unset': 'timer'})

    def getStatus(self):
        return self.sleepServerRequest({'get': 'status'})



class SleepServer(Thread, IssetHelper):
    """
    Control object of system sleep.
    Definition of the dictionary used in the communication queue between this and the network manager:

    {'set': 'immediateSleep'} -> {'status': [STRING]}
    {'set': 'timer', 'time': [INT]} -> {'status': [STRING], 'error': 'bad sleep time'} or {'status': [STRING], 'timeToSleep': [INT]}
    {'unset': 'timer'} -> {'status': [STRING]} or {'status': [STRING], 'acknowledge': 'unsetSleepTime'}
    {'get': 'status'} -> {'status': [STRING]} or {'status': [STRING], 'timeToSleep': [INT]}
    """

    def __init__(self, port):
        # define members:
        self.communicationQueue = Queue()
        self.checkQueueEvent = Event()
        self.networkQueueEvent = Event()

        self.timerRunning = Event()
        self.timeToSleep = -1
        self.initialSleepTime = -1
        self.status = 'running'

        # inital method calls
        Thread.__init__(self)
        self.networkManager = AsyncNetworkManager(self.communicationQueue, self.checkQueueEvent, self.networkQueueEvent, port)
        self.networkManager.start()
        # self.setSleeptime(8) # debug

    def run(self):
        self.timerTick()

        while self.checkQueueEvent.wait():
            self.checkQueueEvent.clear()
            communicatedMessage = self.communicationQueue.get()
            if self.isset(communicatedMessage, 'set'):
                if communicatedMessage['set'] == 'immediateSleep':
                    self.status = 'immediateSleep'
                    self.setStatusResponse()
                    self.sleep()

                elif communicatedMessage['set'] == 'timer' and self.isset(communicatedMessage, 'time'):
                    if self.isInt(communicatedMessage['time']):
                        self.status = 'goingToSleep'
                        self.timeToSleep = int(communicatedMessage['time'])
                        self.initialSleepTime = self.timeToSleep
                        self.timerRunning.set()
                        self.setStatusResponse()
                    else:
                        self.setErrorResponse()

            elif self.isset(communicatedMessage, 'unset'):
                if communicatedMessage['unset'] == 'timer':
                    if self.timeToSleep >= 0:
                        self.resetServer()
                        self.communicationQueue.put({'status': self.status, 'acknowledge': 'unsetSleepTime'})
                        self.networkQueueEvent.set()
                    else:
                        self.setStatusResponse()

            elif self.isset(communicatedMessage, 'get'):
                if communicatedMessage['get'] == 'status':
                    self.setStatusResponse()

            else:
                print('SleepServer: can\'t read queued values!')
                pprint.pprint(communicatedMessage)

    def timerTick(self):
        if self.timerRunning.isSet():
            if self.timeToSleep > 0:
                self.timeToSleep -= 1
                self.volumeControl((100 * self.timeToSleep) / self.initialSleepTime) # make this optional
            else:
                self.sleep()
        Timer(1, self.timerTick).start()

    def setSleeptime(self, time):
        if self.isInt(time):
            time = int(time)
            if time > 0:
                print('SleepServer: set sleep time to', time)
                self.status = 'goingToSleep'
                self.timeToSleep = time
                self.timerRunning.set()
                return True
        return False

    def resetServer(self):
        self.timerRunning.clear()
        self.timeToSleep = -1
        self.status = 'running'

    def setStatusResponse(self):
        if self.timeToSleep >= 0:
            statusDictionary = {'status': self.status, 'timeToSleep': self.timeToSleep}
        else:
            statusDictionary = {'status': self.status}
        self.communicationQueue.put(statusDictionary)
        self.networkQueueEvent.set()

    def setErrorResponse(self):
        if self.timeToSleep >= 0:
            statusDictionary = {'status': self.status, 'timeToSleep': self.timeToSleep}
        else:
            statusDictionary = {'status': self.status}
        statusDictionary['error'] = 'bad sleep time'
        self.communicationQueue.put(statusDictionary)
        self.networkQueueEvent.set()

    def sleep(self):
        print('Sleep now. Good night!')
        self.resetServer()
        subprocess.call(['osascript', '-e', 'tell application "System Events" to sleep'])

    def volumeControl(self, percent):
        if percent > 100:
            percent = 100
        elif percent < 0:
            percent = 0

        targetVolume = (7 * percent) / 100
        subprocess.call(['osascript', '-e', 'Set volume ' + str(targetVolume)])

    # def shutdown(self):
    #     print('SHUTDOWN NOW!')
    #     self.resetServer()
    #     subprocess.call(['osascript', '-e', 'tell application "System Events" to shut down'])



# ************************************************
# non object orientated entry code goes down here:
# ************************************************
def main(port = 4444):
    serverInstance = SleepServer(port)
    serverInstance.start()

# check if this code is run as a module or was included into another project
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Backend for receiving time-to-sleep signals.")
    parser.add_argument("-d", "--daemon", action = "store_true", dest = "daemon", help = "enables daemon mode")
    parser.add_argument("-p", "--port", type=int, help = "specifies the networking port number")
    args = parser.parse_args()

    if args.daemon:
        pidFile = "/tmp/sleepServerDaemon.pid"
        daemon = Daemonize(app='Sleep Server Daemon', pid=pidFile, action=main)
        daemon.start()
    else:
        if args.port:
            main(args.port)
        else:
            main()
