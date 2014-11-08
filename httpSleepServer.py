#!/usr/local/bin/python3.4
# -*- coding: utf-8 -*-
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

import time
from daemonize import Daemonize
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import argparse
import pprint
import json
import threading
from queue import Queue
import subprocess



class RgeeHelper:
    def isset(self, dictionary, key):
        try:
            dictionary[key]
        except (NameError, KeyError) as e:
            return False
        else:
            return True



class HTTPHandler(BaseHTTPRequestHandler, RgeeHelper):
    def setSleepServer(self, sleepServer):
        self.sleepServer = sleepServer

    def do_GET(self):
        queryString = urllib.parse.urlparse(self.path).query
        query = dict(urllib.parse.parse_qsl(queryString))

        returnDict = {}

        if self.isset(query, 'api') and query['api'] == 'sleepServer':
            if self.isset(query, 'get'):
                if query['get'] == 'status':
                    if self.sleepServer.status != 'standby':
                        if self.sleepServer.timeToSleep > 0:
                            returnDict['seconds'] = self.sleepServer.timeToSleep
                        else:
                            # update status information after waking up again
                            self.sleepServer.status = 'standby'
                            self.sleepServer.timeToSleep = -1

                    returnDict = {'status': self.sleepServer.status}

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



class SleepServer:
    def __init__(self, port):
        # define members:
        self.status = 'standby'
        self.serverPort = port

        # inital method calls
        self.startAsyncSystemController()
        # self.startNetworking()
        self.setSleeptime(5)

    def startAsyncSystemController(self):
        self.asyncSystemControllerQueue = Queue()
        self.timerController = threading.Event()

        self.systemController = AsyncSystemControl(event = self.timerController, queue = self.asyncSystemControllerQueue)
        self.systemController.start()

    def startNetworking(self):
        httpHandler = HTTPHandler
        httpHandler.setSleepServer(httpHandler, self)

        try:
            # Create a web server and define the handler to manage the incoming request
            server = HTTPServer(('', self.serverPort), httpHandler)
            print('Started a HTTP-Server on port ', self.serverPort)

            # Wait forever for incoming htto requests
            server.serve_forever()

        except KeyboardInterrupt:
            print(' Received interrupt signal; shutting down the web server!')
            server.socket.close()

    def setSleeptime(self, time):
        if time > 0:
            print('SleepServer: set sleep time to', time)
            self.status = 'goingToSleep'
            self.asyncSystemControllerQueue.put(time)
            # self.timerController.set()
            return True
        return False

    def cancleSleep(self):
        self.timerController.clear()



class AsyncSystemControl(threading.Thread):
    def __init__(self, event, queue):
        threading.Thread.__init__(self)
        self.controlEvent = event
        self.communicationQueue = queue
        self.timeToSleep = -1

    def run(self):
        while not self.controlEvent.wait(1):
            print('timing handler', self.timeToSleep)

            if self.timeToSleep == -1:
                print('get time to sleep out of queue')
                self.timeToSleep = self.communicationQueue.get()
                print('AsyncSystemControl: set sleep time to', self.timeToSleep)

            if self.timeToSleep > 0:
                self.timeToSleep -= 1
            else:
                self.timeToSleep = -1
                self.sleep()
                self.controlEvent.set()

    def sleep(self):
        print('sleep!')
        # subprocess.call(['osascript', '-e', 'tell application "System Events" to sleep'])

    def shutdown(self):
        print('shutdown!')
        # subprocess.call(['osascript', '-e', 'tell application "System Events" to shut down'])



# ************************************************
# non object orientated entry code goes down here:
# ************************************************
def main(port = 4444):
    serverInstance = SleepServer(port)

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
