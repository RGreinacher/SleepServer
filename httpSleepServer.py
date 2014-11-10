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



class HTTPHandler(BaseHTTPRequestHandler, IssetHelper):
    """
    # Defining the SleepServer API:
    ## HTTP-GET:
        api=sleepServer&get:
            get=status -> {'status': 'standby'}
            get=status -> {'status': 'goingToSleep', 'seconds': '[int]'}

        api=sleepServer&set:
            set=sleepTime -> {'errorMessage': 'bad sleep time'}
            set=sleepTime -> {'acknoledge': 'setSleepTime', 'status': 'goingToSleep', 'seconds': '[int]'}

        [any other request] -> {'errorMessage': 'wrong address, no such resource'}

    """
    def setSleepServer(self, sleepServer):
        self.sleepServer = sleepServer

    def do_GET(self):
        queryString = urllib.parse.urlparse(self.path).query
        query = dict(urllib.parse.parse_qsl(queryString))

        returnDict = {}

        if self.isset(query, 'api') and query['api'] == 'sleepServer':
            if self.isset(query, 'get'):
                if query['get'] == 'status':
                    returnDict = self.sleepServer.requestGetStatus()

            if self.isset(query, 'set'):
                if query['set'] == 'sleepTime' and self.isset(query, 'seconds'):
                    if self.sleepServer.setSleeptime(int(query['seconds'])):
                        returnDict = {'acknoledge': 'setSleepTime', 'status': self.sleepServer.status, 'seconds': str(self.sleepServer.timeToSleep)}
                    else:
                        returnDict = {'errorMessage': 'bad sleep time'}

        if returnDict != {}:
            self.send_response(200)
        else:
            self.send_response(404)
            returnDict = {'errorMessage': 'wrong address, no such resource'}

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
            print('AsyncNetworkManager: Started a HTTP-Server on port ', self.serverPort)

            # Wait forever for incoming http requests
            server.serve_forever()

        except KeyboardInterrupt:
            print(' received interrupt signal; shutting down the web server!')
            server.socket.close()

    def requestGetStatus(self):
        # send status request to sleep server via communication queue
        self.communicationQueue.put({'get': 'status'})
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



class SleepServer(Thread, IssetHelper):
    """
    Controll object of system sleep.
    Legend of dictionary used in the communication queue between this and the network manager:

    {'set': 'timer', 'time': [INT]} // sets time to sleep
    {'unset': 'timer'} // stops the timer from setting a sleep time
    {'get': 'status'} -> {'status': [STRING] (, 'timeToSleep': [INT])} // returns the time until sleep in seconds through the communication queue
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

    def run(self):
        print('SleepServer thread up and running...')
        self.timerTick()

        while self.checkQueueEvent.wait():
            self.checkQueueEvent.clear()
            communicatedMessage = self.communicationQueue.get()
            if self.isset(communicatedMessage, 'set'):
                if communicatedMessage['set'] == 'timer' and self.isset(communicatedMessage, 'time'):
                    print('SleepServer: received sleep time, set to', time)
                    self.status = 'goingToSleep'
                    self.timeToSleep = communicatedMessage['time']
                    self.timerRunning.set()

            elif self.isset(communicatedMessage, 'unset'):
                if communicatedMessage['unset'] == 'timer':
                    print('SleepServer: stop timer')
                    self.cancelSleep()

            elif self.isset(communicatedMessage, 'get'):
                if communicatedMessage['get'] == 'status':
                    print('SleepServer: return status via communication queue')
                    if self.status != 'standby':
                        self.communicationQueue.put({'status': self.status, 'timeToSleep': self.timeToSleep})
                    else:
                        self.communicationQueue.put({'status': self.status})
                    self.networkQueueEvent.set()

            else:
                print('SleepServer: can\'t read queued values!')
                pprint.pprint(communicatedMessage)

        print('end of run!')

    def timerTick(self):
        if self.timerRunning.isSet():
            if self.timeToSleep > 0:
                self.timeToSleep -= 1
                print('timer tick. Time is:', self.timeToSleep)
            else:
                self.timeToSleep = -1
                self.timerRunning.clear()
                print('timer stopped! Going to sleep from here')
                self.sleep
        Timer(1, self.timerTick).start()

    def setSleeptime(self, time):
        if time > 0:
            print('SleepServer: set sleep time to', time)
            self.status = 'goingToSleep'
            self.timeToSleep = time
            self.timerTick()
            return True
        return False

    def cancelSleep(self):
        self.timerRunning.clear()
        self.status = 'standby'

    def sleep(self):
        print('SLEEP NOW!')
        # subprocess.call(['osascript', '-e', 'tell application "System Events" to sleep'])

    def shutdown(self):
        print('SHUTDOWN NOW!')
        # subprocess.call(['osascript', '-e', 'tell application "System Events" to shut down'])



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
