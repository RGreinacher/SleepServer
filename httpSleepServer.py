#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-

import time
from daemonize import Daemonize
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import argparse
import pprint
import json
from threading import Thread, Event, Timer
from queue import Queue
import subprocess



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
    """
    # Defining the SleepServer API:
    ## HTTP-GET:
        api/sleepServer/get:
            get/status -> {'status': 'standby'}
            get/status -> {'status': 'goingToSleep', 'seconds': '[int]'}

        api/sleepServer/set:
            set/immediateSleep -> {'status': 'immediateSleep'}
            set/sleepTime/seconds/[INT] -> {'acknoledge': 'setSleepTime', 'status': 'goingToSleep', 'seconds': '[int]'}
            set/sleepTime -> {'errorMessage': 'bad sleep time'}

        api/sleepServer/unset:
            unset/sleepTime -> {'status': 'standby'}

        [any other request] -> {'errorMessage': 'wrong address, wrong parameters or no such resource'}

    ## Test calls:
        - [status request](http://localhost:4444/api/sleepServer/get/status)
        - [set immediate sleep](http://localhost:4444/api/sleepServer/set/immediateSleep)
        - [set sleep time](http://localhost:4444/api/sleepServer/set/sleepTime/seconds/12)
        - [unset sleep time](http://localhost:4444/api/sleepServer/unset/sleepTime)
    """
    def setSleepServer(self, networkManager):
        self.networkManager = networkManager

    def do_GET(self):
        resourceElements = self.path.split('/')
        returnDict = {}
        if 'api' in resourceElements and 'sleepServer' in resourceElements:

            # request for keyword 'get'
            if 'get' in resourceElements:
                if 'status' in resourceElements:
                    returnDict = self.networkManager.getStatus()

            # request for keyword 'set'
            elif 'set' in resourceElements:
                if 'immediateSleep' in resourceElements:
                    returnDict = self.networkManager.sleepImmediate()

                elif 'sleepTime' in resourceElements and 'seconds' in resourceElements:
                    if self.isValueForIndex(resourceElements, 'seconds'):
                        offsetIndex = resourceElements.index('seconds')
                        if self.isInt(resourceElements[offsetIndex + 1]) and int(resourceElements[offsetIndex + 1]) > 0:
                            returnDict = self.networkManager.setSleeptime(int(resourceElements[offsetIndex + 1]))
                            returnDict['acknowledge'] = 'setSleepTime'

                    if returnDict == {}:
                        returnDict = {'errorMessage': 'bad sleep time'}

            # request for keyword 'unset'
            elif 'unset' in resourceElements:
                if 'sleepTime' in resourceElements:
                    returnDict = self.networkManager.unsetSleeptime()

        if returnDict != {}:
            self.send_response(200)
        else:
            self.send_response(404)
            returnDict = {'errorMessage': 'wrong address, wrong parameters or no such resource'}

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
            print('AsyncNetworkManager: HTTP server thread up and running; port', self.serverPort)

            # Wait forever for incoming http requests
            server.serve_forever()

        except KeyboardInterrupt:
            print(' received interrupt signal; shutting down the web server!')
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
    Controll object of system sleep.
    Legend of dictionary used in the communication queue between this and the network manager:

    {'set': 'immediateSleep'} -> {'status': [STRING]}
    {'set': 'timer', 'time': [INT]} -> {'status': [STRING]} or {'status': [STRING], 'timeToSleep': [INT]}
    {'set': 'timer', 'time': [INT]} -> {'status': [STRING], 'error': 'bad sleep time'} or {'status': [STRING], 'timeToSleep': [INT], 'error': 'bad sleep time'}
    {'unset': 'timer'} -> {'status': [STRING]} or {'status': [STRING], 'timeToSleep': [INT]}
    {'get': 'status'} -> {'status': [STRING]} or {'status': [STRING], 'timeToSleep': [INT]}
    """

    def __init__(self, port):
        # define members:
        self.communicationQueue = Queue()
        self.checkQueueEvent = Event()
        self.networkQueueEvent = Event()

        self.timerRunning = Event()
        self.timeToSleep = -1
        self.status = 'standby'

        # inital method calls
        Thread.__init__(self)
        self.networkManager = AsyncNetworkManager(self.communicationQueue, self.checkQueueEvent, self.networkQueueEvent, port)
        self.networkManager.start()
        # self.setSleeptime(8) # debug

    def run(self):
        print('SleepServer: Controller thread up and running')
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
                        self.timerRunning.set()
                        self.setStatusResponse()
                    else:
                        self.setErrorResponse()

            elif self.isset(communicatedMessage, 'unset'):
                if communicatedMessage['unset'] == 'timer':
                    self.resetServer()
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
                print('Timer tick, sleep in', self.timeToSleep)
            else:
                print('Timer stopped, going to sleep now')
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
        self.status = 'standby'

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
