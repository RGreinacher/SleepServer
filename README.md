# SleepServer

Python3 based HTTP API for hibernation and volume control.

## The quick look:

### Why?

Because getting out of bed just to shut down your music playing computer is inconvenient! I want to do that remotly. Or set a timer. Over the air. From out of my bed. And best if it turns down the volume before it hibernates itself!

### How?

SleepServer is designed to work with clients like an iOS / Android App. But the API itself and it's responds (JSON) are also human readable to control the server via any browser - just use the client in you hand.

### What?

SleepServer provides a deadly easy to use RESTful-like API to hibernate your computer and slowly turning down the volume. Simply do a HTTP request with at most three keywords.

One request to tell your computer to hibernate in let's say 42 seconds, and turning the volume down to zero in that time. Or just one request to tell your computer to sleep immediately. Or just one request to stop it from doing that. Use it to set a volume as well as only setting a turn-the-volume-down-to-silence-time - again, both with only one request.

## How it's made

The server is written with ❤ and in Python3 and uses mostly standard Python components and modules. The `sleepServer.py` is the main file and houses four different classes: The control unit (`SleepServer`, independent thread), the network managment unit (`AsyncNetworkManager`, independent thread) and two helper classes (`HTTPHandler` and `IssetHelper`).

The `systemControl.py` is a separate file and handles every system interaction, like setting the system to sleep or accessing the volume. This is made to easily extend the supported platforms. As a developer, you can easily add the specific command of the mentioned tasks for your platform in that class. This way you do not have to read through the hunderets of lines of code of the `sleepServer.py`

**Supported platforms:**
- Mac OSX 10.6
- Mac OSX 10.10
- ARCH Linux *(Kernel 3.17, SystemD)*

Try it on serveral other platforms and extend the system interaction commands if necessary. The code therefor (`systemControl.py`) is self-explaining.

## Get it running
Install Python3 and make sure the following required modules are available:

- [threading](https://docs.python.org/3/library/threading.html)
- [queue](https://docs.python.org/3/library/queue.html)
- [Daemonize](https://github.com/thesharp/daemonize) (`pip3 install daemonize`)
- [argparse](https://docs.python.org/3/library/argparse.html)
- [http.server](https://docs.python.org/3/library/http.server.html)
- [json](https://docs.python.org/3/library/json.html)
- [subprocess](https://docs.python.org/3/library/subprocess.html)
- [platform](https://docs.python.org/3/library/platform.html)
- [pprint](https://docs.python.org/3/library/pprint.html)

Run the server with default parameters (not a daemon, port 4444). You won't need administration privileges to run SleepServer until you change the port number to under 1024:

	python3 sleepServer.py
	
You can customize the port by adding a flag:

	python3 sleepServer.py -p 1337
	
Or start the server as a daemon and run in the backgound:

	python3 sleepServer.py -d

You can even enable a verbous mode to get informed about nearly everything that happens on the inside:

	python3 sleepServer.py -v

And you can ask for the list of possible options with:

	python3 sleepServer.py -h

***

# API usage:
The whole API uses only HTTP GET requests to keep things simple and make it easy to test.
(Future versions may change that to make use of HTTP PUT, PATCH and UPDATE, as well as be able to specify an API version.
The pattern for API versioning will be `sleepApi/1.0/[task]`. This pattern can already be implemented by clients now, but will not affect the behaviour.)

The response format is always JSON. Possible HTTP status codes are 200, 202, 400 and 404.
Every request returns either an acknowledgement and the current status, just the current status or an error message.

## get status information
    call: sleepApi/status
    receive: {'status': 'running', 'currentVolume': [decimal]} (HTTP: 200)
    receive: {'status': 'goingToSleep', 'timeToSleep': '[int]', 'currentVolume': [decimal]} (HTTP: 200)
    receive: {'status': 'goingToSilence', 'timeToSilence': '[int]', 'currentVolume': [decimal]} (HTTP: 200)
    receive: {'status': 'goingToSleepAndSilence', 'timeToSleep': '[int]', 'currentVolume': '[decimal]'} (HTTP: 200)

## set the sleep time / immediate sleep

Set only the sleep time:

    call: sleepApi/setSleepTime/[int]
    receive: {'status': 'goingToSleep', 'timeToSleep': '[int]'} (HTTP: 202)
    receive error: {'errorMessage': 'bad sleep time'} (HTTP: 400)

Set immediate sleep:

    call: sleepApi/immediateSleep
    receive: {'status': 'immediateSleep'} (HTTP: 202)
    

## set the silence time / volume

Set the volume (percentage, decimal):

    call: sleepApi/setVolume/[decimal]
    receive: {'status': 'running', 'currentVolume': [decimal]} (HTTP: 202)
    receive: {'status': 'goingToSleep', 'timeToSleep': '[int]', 'currentVolume': [decimal]} (HTTP: 200)
    receive error: {'errorMessage': 'bad volume percentage'} (HTTP: 400)

Set only the silence time:

    call: sleepApi/setSilenceTime/[int]
    receive: {'status': 'goingToSilence', 'timeToSilence': '[int]'} (HTTP: 202)
    receive error: {'errorMessage': 'bad silence time'} (HTTP: 400)

## set good night time

The good night time is a combination of both, the sleep and the silence time. If this time is greater than 10 minutes, the time until then will be at a constant volume and it will be turned down only within the last 10 minutes. If the good night time is shorter than 10 minutes the volume will be decreased linearly from the beginning of the call.

	call: sleepApi/setGoodNightTime/[int]
	receive: {'status': 'goingToSleepAndSilence', 'timeToSleep': '[int]', 'currentVolume': '[decimal]'} (HTTP: 202)
	receive error: {'errorMessage': 'bad good night time'} (HTTP: 400)


## unset timer / reset the server:

Use one command for unsetting all timers and resetting the server. This command will be executed every time before a request is processed, except for the `setVolume` command and the `status` command:

    call: sleepApi/reset
    receive: {'status': 'running', 'currentVolume': [decimal]} (HTTP: 202)
    receive: {'status': 'running', 'acknowledge': 'unsettingTimer', 'currentVolume': [decimal]} (HTTP: 202)

## others:
    call: [any other request]
    receive error: {'errorMessage': 'wrong address, wrong parameters or no such resource'} (HTTP: 404)

### Test calls:
- [status request](http://localhost:4444/sleepApi/status) http://localhost:4444/sleepApi/status
- [set sleep time](http://localhost:4444/sleepApi/setSleepTime/42) http://localhost:4444/sleepApi/setSleepTime/42
- [set immediate sleep](http://localhost:4444/sleepApi/immediateSleep) http://localhost:4444/sleepApi/immediateSleep
- [set silence time](http://localhost:4444/sleepApi/setSilenceTime/42) http://localhost:4444/sleepApi/setSilenceTime/42
- [set good night time](http://localhost:4444/sleepApi/setGoodNightTime/42) http://localhost:4444/sleepApi/setGoodNightTime/42
- [set system volume](http://localhost:4444/sleepApi/setVolume/75.8) http://localhost:4444/sleepApi/setVolume/75.8
- [unset timer](http://localhost:4444/sleepApi/reset) http://localhost:4444/sleepApi/reset

***

# Apart of the code

## Contribution & Contributors

I'd love to see your ideas for improving this project!
The best way to contribute is by submitting a pull request or a [new Github issue](https://github.com/RGreinacher/SleepServer/issues/new). :octocat:

## Author:

[Robert Greinacher](mailto:network@robert-greinacher.de?subject=GitHub SleepServer) / [@RGreinacher](https://twitter.com/RGreinacher) / [LinkedIn](https://www.linkedin.com/profile/view?id=377637892)

Thank you for reading this and for your interest in my work. I hope I could help you or even make your day a little better. Cheers!

## License:

SleepServer is available under the MIT license. See the LICENSE file for more info.

*[Thanks [Tom](https://github.com/TomKnig) for the inspiration of this last passage.]*