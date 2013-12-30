import logging
import os
import sys
import webbrowser

import subliminal

import cherrypy
import autosubliminal
from autosubliminal import scheduler, diskscanner, subchecker, webserver


log = logging.getLogger(__name__)


def daemon():
    print "Auto-Subliminal: Starting as a daemon"
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)

    os.chdir(autosubliminal.PATH)
    os.setsid()
    os.umask(0)
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)

    print "Auto-Subliminal: Disabling console output for daemon."

    cherrypy.log.screen = False
    sys.stdin.close()
    sys.stdout.flush()
    sys.stderr.flush()


def launch_browser():
    host = autosubliminal.WEBSERVERIP
    port = autosubliminal.WEBSERVERPORT
    wr = autosubliminal.WEBROOT
    if host == '0.0.0.0':
        host = 'localhost'

    url = 'http://%s:%d' % (host, int(port))
    url = url + wr
    try:
        webbrowser.open(url, 2, 1)
    except:
        try:
            webbrowser.open(url, 1, 1)
        except:
            log.error('Browser launh failed')


def start():
    # Only use authentication in CherryPy is a username and password is set by the user
    if autosubliminal.USERNAME and autosubliminal.PASSWORD:
        users = {autosubliminal.USERNAME: autosubliminal.PASSWORD}
        cherrypy.config.update({'server.socket_host': autosubliminal.WEBSERVERIP,
                                'server.socket_port': autosubliminal.WEBSERVERPORT,
                                'tools.digest_auth.on': True,
                                'tools.digest_auth.realm': 'Auto-Subliminal website',
                                'tools.digest_auth.users': users
        })
    else:
        cherrypy.config.update({'server.socket_host': autosubliminal.WEBSERVERIP,
                                'server.socket_port': autosubliminal.WEBSERVERPORT
        })

    conf = {
        '/': {
            'tools.encode.encoding': 'utf-8',
            'tools.decode.encoding': 'utf-8',
            'tools.staticdir.root': os.path.join(autosubliminal.PATH, 'interface/media/'),
        },
        '/css': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "css",
            'tools.expires.on': True,
            'tools.expires.secs': 3600 * 24 * 7
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "images",
            'tools.expires.on': True,
            'tools.expires.secs': 3600 * 24 * 7
        },
        '/scripts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "scripts",
            'tools.expires.on': True,
            'tools.expires.secs': 3600 * 24 * 7
        },
        '/mobile': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "mobile",
            'tools.expires.on': True,
            'tools.expires.secs': 3600 * 24 * 7
        },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.join(autosubliminal.PATH, 'interface/media/images/favicon.ico')
        }
    }

    cherrypy.tree.mount(autosubliminal.webserver.WebServerInit(), autosubliminal.WEBROOT, config=conf)
    log.info("Starting CherryPy webserver")

    # TODO: Let CherryPy log do another log file and not to screen
    # TODO: CherryPy settings, etc...
    try:
        cherrypy.server.start()
    except Exception, e:
        log.error("Could not start webserver. Exiting")
        log.exception(e)
        os._exit(1)

    cherrypy.server.wait()

    if autosubliminal.LAUNCHBROWSER:
        launch_browser()

    # Configure subliminal/dogpile cache
    # Use MutexLock otherwise some providers will not work due to fcntl module import error in windows
    cache_file = os.path.abspath(os.path.expanduser(autosubliminal.SUBLIMINALCACHEFILE))
    subliminal.cache_region.configure(autosubliminal.DOGPILECACHEFILE,
                                      arguments={'filename': cache_file, 'lock_factory': subliminal.MutexLock})

    log.info("Starting SCANDISK thread")
    autosubliminal.SCANDISK = autosubliminal.scheduler.Scheduler(autosubliminal.diskscanner.DiskScanner(),
                                                                 autosubliminal.SCHEDULERSCANDISK, True,
                                                                 "SCANDISK")
    autosubliminal.SCANDISK.thread.start()
    log.info("SCANDISK thread started")

    log.info("Starting CHECKSUB thread")
    autosubliminal.CHECKSUB = autosubliminal.scheduler.Scheduler(autosubliminal.subchecker.SubChecker(),
                                                                 autosubliminal.SCHEDULERCHECKSUB, True,
                                                                 "CHECKSUB")
    autosubliminal.CHECKSUB.thread.start()
    log.info("CHECKSUB thread started")


def stop():
    log.info("Stopping SCANDISK thread")
    autosubliminal.SCANDISK.stop = True
    autosubliminal.SCANDISK.thread.join(10)

    log.info("Stopping CHECKSUB thread")
    autosubliminal.CHECKSUB.stop = True
    autosubliminal.CHECKSUB.thread.join(10)

    cherrypy.engine.exit()

    os._exit(0)


def signal_handler(signum, frame):
    log.debug("Got signal. Shutting down")
    os._exit(0)
