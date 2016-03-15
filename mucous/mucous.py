#! /usr/bin/env python
#-*- coding: utf-8 -*-

##########################################################################
# Mucous - a Python/Curses client for Museek                             #
##########################################################################
#
# Majority of code (C) 2005-2006 daelstorm <daelstorm@gmail.com>
#
# Based on Museekchat
# Copyright (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
# Config-parsing code modified from Nicotine's config.py
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
try:
    from Crypto.Hash import SHA256

except ImportError:

    try:
        import mucipher
    except:
        print("WARNING: The Mucipher Module for Python wasn't found and neither was PyCrypto. One of these is necessary to allow Mucous to connect to the Museek Daemon.\nDownload mucipher here: http://thegraveyard.org/files/pymucipher-0.0.1.tar.gz\nExtract the tarball, and as Root or sudo, run:\npython setup.py install\nYou'll need GCC, Python and SWIG.\nOr download PyCrypto from here: http://www.amk.ca/python/code/crypto.html")
        sys.exit()

REQUIRE_PYMUSEEK = '0.3.0'

def versionCheck(version):
    build = 255
    def _required():
        global REQUIRE_PYMUSEEK
        r = REQUIRE_PYMUSEEK.split(".")
        r_major, r_minor, r_micro = [int(i) for i in r[:3]]
        return (r_major << 24) + (r_minor << 16) + (r_micro << 8) + build

    s = version.split(".")
    major, minor, micro = [int(i) for i in s[:3]]

    if (major << 24) + (minor << 16) + (micro << 8) + build >= _required():
        return True
    return False

try:
    import messages, driver
except Exception as error:
    try:
        import museek
        from museek import messages, driver
        if not hasattr(museek, 'VERSION'):
            raise Exception("Cannot use unknown museek python bindings version.")
        elif hasattr(museek, 'VERSION') and not versionCheck(museek.VERSION):
            raise Exception("Cannot use museek python bindings version: %s" % (museek.VERSION))
    except Exception as error:
        print("WARNING: The Museek Message-Parsing modules, messages.py and/or driver.py were not found, or are an old version. Please install them into your '/usr/lib/python2.X/site-packages/museek' directory, or place them in a 'museek' subdirectory of the directory that contains the mucous python script.")
        print(error)

        sys.exit()

import signal, time, os, commands, getopt, thread, threading, select, string, re
from pymucous import ConfigParser
import curses.wrapper, curses.ascii
import traceback
from time import sleep



pcg = 0
try:
    from pymucous.MucousTransfers import Transfers
    from pymucous.MucousUserInfo import UserInfo
    from pymucous.MucousFormat import FormatData, SortedDict
    from pymucous.MucousMuscan import Muscan
    from pymucous.MucousPrivateChat import PrivateChat
    from pymucous.MucousPopup import PopupMenu
    from pymucous.MucousHelp import Help
    from pymucous.MucousLists import UsersLists
    from pymucous.MucousInput import CharacterParse
    from pymucous.MucousNetworking import Networking
    from pymucous.MucousSearch import Search
    from pymucous.MucousSetup import Setup
    from pymucous.MucousRoomsList import RoomsList
    from pymucous.MucousRecommendations import Recommendations
    from pymucous.MucousChatRooms import ChatRooms
    from pymucous.MucousShares import BrowseShares
    from pymucous.MucousAlerts import Alerts
except ImportError as e:
    print("Failed loading Mucous modules:", e)


try:
    geoip_fail=0
    import GeoIP
    gi = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE)
except ImportError:
    geoip_fail=1
    print("Optional Python Module GeoIP not found, you can safely disregard this message.")

config_dir = str(os.path.expanduser("~/.mucous/"))
log_dir = None #str(os.path.expanduser("~/.mucous/logs/"))
config_file = config_dir+"config"
Version = "0.9.3"

## Command Options
def usage():
    print("""Mucous is a client for Museek, the P2P Soulseek Daemon
Author: Daelstorm
Credit: Hyriand
Version: %s
    Default options: none
    -c, --config <file> Use a different config file
    -l, --log <dir> Use a different logging directory
    -v, --version   Display version and quit
    -d, --debug     Debug mode
    -p, --profile   Use the python profiler
    -g, --pycallgraph   Use pycallgraph
    -h, --help      Display this help and exit
    """ %Version)
    sys.exit(2)

try:
    opts, args = getopt.getopt(sys.argv[1:], "hc:vdl:pg", ["profile", "pycallgraph", "help", "config=", "version", "log=", "debug"])
except getopt.GetoptError:
    usage()
    sys.exit(2)
    profile = 0
    debug=False
for opts, args in opts:

    if opts in ("-p", "--profile"):
        profile = 1
    elif opts in ("-g", "--pycallgraph"):
        pcg = 1
    elif opts in ("-d", "--debug"):
        debug = True
    elif opts in ("-h", "--help"):
        usage()
        sys.exit()
    if opts in ("-c", "--config"):
        config_file=str(os.path.expanduser(args))
    if opts in ("-l", "--log"):
        log_dir=str(os.path.expanduser(args))
    if opts in ("-v", "--version"):
        print("Mucous version: %s" % Version)
        sys.exit(2)


## Modify and read the Mucous Config
#
class ConfigManager:
    ## Constructor
    # @param self ConfigManager
    # @param mucous Mucous (Class)
    def __init__(self, mucous):
        ## @var parser
        # ConfigParser instance

        self.parser = ConfigParser.ConfigParser()
        ## @var mucous
        # Mucous (class)
        self.mucous = mucous

    ## Create config dict from config file
    # @param self ConfigManager
    def create_config(self):

        self.parser.read([config_file])

        mucous_config_file = file(config_file, 'w')

        for i in self.mucous.Config.keys():
            if not self.parser.has_section(i):
                self.parser.add_section(i)
            for j in self.mucous.Config[i].keys():
                if j not in ["nonexisting", "hated", "options"]:
                    self.parser.set(i,j, self.mucous.Config[i][j])
                else:
                    self.parser.remove_option(i,j)
                    self.parser.write(mucous_config_file)
                    mucous_config_file.close()

    ## Create config file and parse options
    # @param self ConfigManager
    def read_config(self):

        self.parser.read([config_file])
        for i in self.parser.sections():
            for j in self.parser.options(i):
                val = self.parser.get(i,j, raw = 1)

                if j in ['login','passw','interface', 'roombox', 'tickers_enabled', "ticker_cycle", "ticker_scroll", "scrolltime", "cycletime", 'default_room', "autobuddy", "now-playing", "log_dir", "aliases" "now-playing-prefix", "browse_display_mode", "url reader", "url custom", "transbox", "autoaway", "rooms_sort", "logging", "beep", "auto-clear", "auto-retry", "extra_requests"] :
                    if val != "None":
                        self.mucous.Config[i][j] = val
                elif i == 'aliases':
                    if val != "None":
                        self.mucous.Config[i][j] = val
                else:
                    try:
                        self.mucous.Config[i][j] = eval(val, {})
                    except:
                        self.mucous.Config[i][j] = None

    ## Write config file to disk
    # @param self ConfigManager
    def update_config(self):
        mucous_config_file = file(config_file, 'w')
        for i in self.mucous.Config.keys():
            if not self.parser.has_section(i):
                self.parser.add_section(i)
            for j in self.mucous.Config[i].keys():
                if j not in ["somethingwrong"]:
                    self.parser.set(i,j, self.mucous.Config[i][j])
                else:
                    self.parser.remove_option(i,j)
                    self.parser.write(mucous_config_file)
                    mucous_config_file.close()
                    self.mucous.Help.Log("status", "Config Saved")

    ## Check the filesystem for the existance of the config file
    # Create it if it doesn't exist
    # Read it if it does exist
    # @param self ConfigManager
    def check_path(self):
        if os.path.exists(config_dir):
            if os.path.exists(config_file) and os.stat(config_file)[6] > 0:
                self.read_config()
            else:
                self.create_config()

        else:
            os.mkdir(config_dir, 0o700)
            self.create_config()



## Main class
class Mucous:
    ## Constructor
    ## @author daelstorm
    ## @brief Subclass driver.Driver, load default variables, create interface, attempt connection to museekd
    # @param self Mucous (class)
    def __init__(self):
        ## @var config
        # config copied from museekd
        self.config = {}
        ## @var usernames
        # Dict of special usernames
        self.usernames = {"privileges": None }
        ## @var username
        # Your username
        self.username = None
        ## @var config_dir
        # Config Directory -- where to save data
        self.config_dir = config_dir
        ## @var geoip_fail
        # Did GeoIP fail to load? (True/False)
        self.geoip_fail = geoip_fail
        ## @var Version
        # Version of program
        self.Version = Version
        ## @var gi
        # GeoIP Instance (Class)
        if not self.geoip_fail:
            self.gi = gi
        else:
            self.gi = None
            self.traceback = traceback
            ## @var Config
            # default config
        self.Config = {"connection":{"interface":'localhost:2240', "passw":None}, \
                       "mucous":{"autobuddy": "no", "roomlistminsize": 5, "rooms_sort": "size", \
                                 "roombox": "big", "log_dir": "~/.mucous/logs/", "now-playing": "default", \
                                 "now-playing-prefix": None, "browse_display_mode": "filesystem", "browse_width": 25, \
                                 "url reader": "firefox", "url custom": "$", \
                                 "transbox" : "split", "language": "iso-8859-1", "beep": "yes", "autoaway": "yes", \
                                 "auto-retry": "yes", "auto-clear": "no", "logging": "yes", "extra_requests": "Yes"}, \
                       "tickers":{'tickers_enabled': 'yes', "ticker_cycle": "no", "rooms":{}, "ticker_scroll": "yes", "scrolltime": "0.3", "cycletime": "3.0"}, \
                       "aliases": {"mucous":"Mucous is a Curses client for the Museek Soulseek Daemon. Website: http://thegraveyard.org/daelstorm/mucous.php", "museek":"Museek+ is a Soulseek Daemon/Client. The website is http://museek-plus.org/"},\
                       "rooms": {"default_room":None}\
        }
        ## @var config_manager
        # ConfigManager (Class)
        self.config_manager = ConfigManager(self)
        self.config_manager.check_path()

        # Config corrections
        if log_dir != None and log_dir != "":
            self.Config["mucous"]["log_dir"] = str(os.path.expanduser(log_dir))

        elif "log_dir" in self.Config["mucous"]:
            if self.Config["mucous"]["log_dir"] in ("", None, "None"):
                self.Config["mucous"]["log_dir"] = str(os.path.expanduser("~/.mucous/logs/"))

        if str(self.Config["mucous"]["logging"]) == "True":
            self.Config["mucous"]["logging"] = "yes"

        ## @var Spl
        # Special Variables
        self.Spl = {"title": None,  "status": None, "connected": 0, \
                    "history_count": 0, "ticker_room": None, "ticker_num":  0, \
                    "museekconfigfile": ""}
        ## @var data
        # data dict (variable storage)
        self.data = { "mystats": [], }
        ## @var logs
        # store lists of data here
        self.logs = {"tab_completion": [], "search_count": ["Results: ", 0], "history": [""],  "onlinestatus": "Offline",     }
        ## @var activeitems
        # Tab button positions
        self.activeitems = {"positions": {}}
        ## @var requests
        # dict of users with requested data
        self.requests = {"ip":[],  "statistics": []}
        ## @var mode
        # which part of Mucous is displayed
        self.mode = "chat"
        ## @var user
        # Dicts of User status and statistics
        self.user = { "status": {}, "statistics": {}  }
        ## @var windows
        # Curses window instances
        self.windows = {"text": {}, "border": {}, "browse": {}, "tab": {} }
        ## @var dimensions
        # Window dimensions / coordinates
        self.dimensions = {}
        ## @var SortedDict
        # SortedDict (Class)
        self.SortedDict = SortedDict
        ## @var D
        # Networking (Class)
        self.D = Networking(self)
        ## @var Help
        # Help (Class)
        self.Help = Help(self)
        ## @var FormatData
        # FormatData (Class)
        self.FormatData = FormatData(self)
        ## @var PopupMenu
        # PopupMenu (Class)
        self.PopupMenu = PopupMenu(self)
        ## @var Muscan
        # Muscan (Class)
        self.Muscan = Muscan(self)
        ## @var UserInfo
        # UserInfo (Class)
        self.UserInfo = UserInfo(self)
        ## @var ChatRooms
        # ChatRooms (Class)
        self.ChatRooms = ChatRooms(self)
        ## @var PrivateChat
        # PrivateChat (Class)
        self.PrivateChat = PrivateChat(self)
        ## @var BrowseShares
        # BrowseShares (Class)
        self.BrowseShares = BrowseShares(self)
        ## @var RoomsList
        # RoomsList (Class)
        self.RoomsList = RoomsList(self)
        ## @var Recommendations
        # Recommendations (Class)
        self.Recommendations = Recommendations(self)
        ## @var Setup
        # Setup (Class)
        self.Setup = Setup(self)
        ## @var UsersLists
        # UsersLists (Class)
        self.UsersLists = UsersLists(self)

        ## @var Search
        # Search (Class)
        self.Search = Search(self)

        ## @var Alerts
        # Alerts (Class)
        self.Alerts = Alerts(self)
        ## @var Transfers
        # Transfers (Class)
        self.Transfers = Transfers(self)


        ## @var url
        # A Url collected from chat logs
        self.url = None
        ## @var timedout
        # Away status timed out after a period of user inactivity
        self.timedout = False
        ## @var listline
        # Tab Completion Line (split into a list)
        self.listline = []
        ## @var line
        # Input Line
        self.line = ""
        ## @var edit
        # CharacterParse (Class)
        self.edit = CharacterParse(self)
        ## @var keepit
        # Keep autocompletion list while tabbing
        self.keepit = []

        ## @var invalidpass
        # If True, password to museekd was invalid
        self.invalidpass = False

        self.subprocess_fail=0
        try:
            import subprocess
            self.subprocess = subprocess
        except ImportError:
            self.subprocess_fail=1
            ## @var encodings
            # List of encodings, used in encodings popup :: Recommended: ISO-8859-1
            # UTF-16 AND ISO-8859-12 crash Mucous
            # UTF-8 is bad, since it's usually the original encoding being converted from
        self.encodings  = ['iso-8859-1', 'iso-8859-2', 'iso-8859-3', 'iso-8859-4', 'iso-8859-5', 'iso-8859-6', 'iso-8859-7', 'iso-8859-8', 'iso-8859-9', 'iso-8859-10', 'iso-8859-11', 'iso-8859-13', 'iso-8859-14', 'iso-8859-15', 'utf-8', 'utf-7',  'ascii']
        if "language" in self.Config["mucous"]:
            if self.Config["mucous"]["language"] not in self.encodings:
                self.Config["mucous"]["language"] = "iso-8859-1"
        else:
            self.Config["mucous"]["language"] = "iso-8859-1"

        ## @var timers
        # Dictionary of timers
        self.timers = {}

        #transfers :: Calls: ThreadTransfersRetry
        self.timers["retry"] = threading.Timer(30.0, self.ThreadTransfersRetry)
        ## @var timers["clear"]
        # Clear tramsfers timer :: Calls: Mucous.ThreadTransfersClear
        self.timers["clear"] = threading.Timer(30.0, self.ThreadTransfersClear)
        ## @var timers["nick"]
        # Clear tramsfers timer :: Calls: Mucous.ThreadTransfersClear
        self.timers["nick"] = threading.Timer(10.0, self.ThreadNickCheck)
        ## @var timeout_time
        # How long before away timer starts (900 seconds)
        self.timeout_time =  900 * 1.0
        ## @var timers["timeout"]
        # AutoAway time instance
        self.timers["timeout"] = threading.Timer(self.timeout_time, self.AwayTimeout)



        if "ticker_cycle" in self.Config["tickers"].keys():
            pass
        else:
            self.Config["tickers"]["ticker_cycle"] = "yes"
            ## @var commandlist
            # List of /commands (for Tab-completion)
        self.commandlist =  ["/me", "/j", "/join", "/p", "/part", "/l", "/leave", "/talk", "/say", "/alias", "/list", "/users", \
                             "/cd",  "/get", "/getdir", "/nick", "/privs", "/privileges", "/giveprivs",\
                             "/help", "/info",  "/autojoin", "/roombox", "/autoaway", "/transbox", "/roomlist", "/roomlistrefresh", \
                             "/inrooms", "/pm",  "/msg", "/np", "/npset", "/npcheck", "/browsewidth", \
                             "/npprefix", "/tickroom", "/tickcycle",  "/listtick", "/tickers", "/interface", "/password",\
                             "/save", "/connect", "/disconnect", "/autobuddy", "/autoclear", "/autoretry", "/privbuddy", "/onlybuddy",\
                             "/slots","/buddy", "/unbuddy",  "/ban", "/banlist", "/beep", "/trust", "/distrust", "/unban", "/nuke", "/unnuke",\
                             "/ignore", "/unignore",  "/unhide",  "/userinfo", "/ip", "/stat", "/away", "/abortup", "/percent", \
                             "/abortdown",  "/removeup", "/removedown", "/retry", "/retryall", "/clearup", "/cleardown", "/clearroom", "/clearsearchs", "/url", "/urlreader", "/urlcustom",\
                             "/search", "/searchfor", "/searchbuddy", "/searchroom", "/download", "/downdir", "/browse",\
                             "/browseuser", "/browsesearch", "/browsedown",  "/downuser",\
                             "/downpath", "/downpathdir",  "/chat", "/ignorelist", "/banlist", "/transfer", "/transfers", "/private",\
                             "/buddylist", "/setup", "/quit", "/logging", "/logdir", "/reloadshares", "/rescanshares", "/version", "/extra", "/exist", \
                             "/logout", "/login", "/like", "/donotlike", "/donothate", "/hate", "/similar", "/globalrex", "/recommendations", "/rex", "/itemsimilar", "/itemrex", "/uploadto", "/upload", "/ctcpversion", "/defaulttick", "/settemptick", "/settick "]

        for alias in self.Config["aliases"].keys():
            self.commandlist.append("/"+alias)
            ## @var stdscr
            # Curses screen Startup
        self.stdscr = curses.initscr()
        curses.def_shell_mode()
        #curses.flushinp()
        #curses.setupterm()
        #self.log["help"].append(str(curses.termattrs() ) )
        #self.log["help"].append(str(curses.termname() ))
        curses.meta(1)
        h, w = self.stdscr.getmaxyx()
        #h,w = struct.unpack("HHHH", fcntl.ioctl(sys.stdout.fileno(),termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0)))[:2]
        if  h <=7 or w <=37:
            self.stdscr.keypad(1)
            curses.echo()
            curses.endwin()
            print("Console kinda small, resize it, please")
            sys.exit()
            #---------------

        curses.start_color()
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.mouseinterval(110)
        ## @var colors
        # Dict of color pairs
        self.colors = {}
        if curses.has_colors() == True:
            try:
                curses.use_default_colors()

                curses.init_pair(1, curses.COLOR_RED, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_CYAN, -1)
                curses.init_pair(4, curses.COLOR_BLUE, -1)
                curses.init_pair(5, curses.COLOR_GREEN, -1)

                curses.init_pair(6, curses.COLOR_BLACK, -1)
                curses.init_pair(7, curses.COLOR_WHITE, -1)
                curses.init_pair(8, curses.COLOR_MAGENTA, -1)
                curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_CYAN)
                #if curses.can_change_color():
                #curses.init_pair(5, 33, -1)
                #curses.init_pair(10, curses.COLOR_GREEN, curses.COLOR_BLACK )
                #curses.init_pair(11, curses.COLOR_YELLOW, curses.COLOR_BLUE)
                #curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_WHITE)
            except AttributeError:
                curses.init_pair(1, curses.COLOR_RED, 0)
                curses.init_pair(2, curses.COLOR_YELLOW, 0)
                curses.init_pair(3, curses.COLOR_CYAN, 0)
                curses.init_pair(4, curses.COLOR_BLUE, 0)
                curses.init_pair(5, curses.COLOR_GREEN, 0)
                curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
                curses.init_pair(7, curses.COLOR_WHITE, 0)
                curses.init_pair(8, curses.COLOR_MAGENTA, 0)
                curses.init_pair(9, 0, curses.COLOR_CYAN)

            curses.init_pair(10, curses.COLOR_GREEN, curses.COLOR_BLACK )
            curses.init_pair(11, curses.COLOR_YELLOW, curses.COLOR_BLUE)
            curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_WHITE)

            curses.init_pair(13, curses.COLOR_YELLOW, curses.COLOR_CYAN)
            curses.init_pair(14, curses.COLOR_BLACK, curses.COLOR_GREEN)
            curses.init_pair(15, curses.COLOR_BLACK, curses.COLOR_RED)
            curses.init_pair(16, curses.COLOR_WHITE, curses.COLOR_RED)
            curses.init_pair(17, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(18, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
            self.colors["cyanyellow"] = curses.color_pair(13)
            self.colors["blackgreen"] = curses.color_pair(14)
            self.colors["blackred"] = curses.color_pair(15)
            self.colors["whitered"] = curses.color_pair(16)
            self.colors["blackyellow"] = curses.color_pair(17)
            self.colors["blackmagenta"] = curses.color_pair(18)
            self.colors["normal"] = curses.color_pair(0)
            self.colors["red"] = curses.color_pair(1)
            self.colors["yellow"] = curses.color_pair(2)
            self.colors["cyan"] =  curses.color_pair(3)
            self.colors["blue"] = curses.color_pair(4)
            self.colors["green"] =  curses.color_pair(5)
            #self.colors["green"] =  curses.color_pair(27)
            self.colors["black"] = curses.color_pair(6)
            self.colors["white"] = curses.color_pair(7)
            self.colors["magenta"] = curses.color_pair(8)
            self.colors["cybg"] = curses.color_pair(9)
            self.colors["greenblack"] = curses.color_pair(10)
            self.colors["hotkey"] = curses.color_pair(11)
            self.colors["blackwhite"] = curses.color_pair(12)
        else:
            self.colors["cyanyellow"] = self.colors["blackgreen"] = self.colors["blackred"] = self.colors["whitered"] = self.colors["blackmagenta"] = self.colors["blackyellow"] = self.colors["normal"] = self.colors["blackwhite"]  = self.colors["hotkey"] = self.colors["greenblack"] = self.colors["cybg"] = self.colors["magenta"] = self.colors["white"] =self.colors["black"]  = self.colors["cyan"] =  self.colors["yellow"] =self.colors["blue"]  =self.colors["green"] = self.colors["red"] =  curses.color_pair(0)
            #Disable cursor (bad idea)
            curses.curs_set(1)
            # Enable Function Keys
        self.stdscr.keypad(1)
        self.Spl["input_horizontal"] = self.Spl["input_vertical"] = 0

        self._run = True
        thread.start_new_thread(self.InputThread, ())
        self.run()

    def run(self):
        curses.noecho()
        curses.cbreak()
        while self._run:

            try:
                self.line = self.Build()
            except Exception as e:
                self.Help.Log("debug", str(e) )
                sleep(0.1)
            if self.D.socket is None:
                try:
                    self.D.connect()
                except select.error as e:
                    # Terminal resized
                    self.line = self.Build()
                except KeyboardInterrupt as error:
                    # Ctrl-C
                    self.shutdown(error)
            try:
                self.D.processWrap()
            except select.error as e:
                # Terminal resized
                self.line = self.Build()

            except KeyboardInterrupt as e:
                # Ctrl-C
                self.shutdown(e)
                break

        curses.nocbreak()
        curses.echo()
        curses.endwin()

    def InputThread(self):

        keys = []
        try:
            while 1:
                # Place Cursor
                c = self.GetKey()
                if c != None:
                    keys.append(c)

                while keys:
                    # process each key, one at a time
                    c, keys = keys[0], keys[1:]
                    if self.edit.process(c):
                        self.line = self.edit.line
                        feedback = self.edit.InputCommands(self.line)

                        if feedback == 0:
                            break
                        elif feedback == 2:
                            # Exit
                            self.Help.Mode()
                            self._run = False
                            return
                        else:
                            self.edit.reset()
                            sleep(0.001)
        except Exception as e:
            self.Help.Mode()
            self.Help.Log("debug", "Processing... " + str(e))

    ## Find the current Cursor Position and get a keypress
    # @param self Networking (Driver Class)
    def GetKey(self):
        #try:
        # Find Cursor Position
        y = self.Spl["input_vertical"]
        x = self.Spl["input_horizontal"] + self.edit.x

        if self.edit.wrap:

            ScrollLine = self.edit.scroll/self.edit.w
            y = self.Spl["input_vertical"] + ScrollLine
            ScrollRemainder = self.edit.scroll % self.edit.w
            x = ScrollRemainder + self.Spl["input_horizontal"]

        try:
            c = self.stdscr.getkey( y, x)

            return c
        except curses.error as e:
            pass
        return None


    ## Create curses input window
    def UseAnotherEntryBox(self, window=None, height=None, width=None, top=None, left=None, contents=None, wrap=None):
        if window:
            self.Spl["input_vertical"] = top
            self.Spl["input_horizontal"] = left
        else:
            if self.edit.win == self.windows["input"]:
                return
            w = self.dimensions["input"]
            window = self.windows["input"]
            self.Spl["input_vertical"] = w["top"]
            self.Spl["input_horizontal"] = w["left"]
            self.edit.line = ""
            self.edit.SelectEntryBox(window, contents, wrap)


    ## Create curses input window
    # @param self Mucous (class)
    def CreateEntryBox(self):
        try:
            # Clean stale windows
            if "input" in self.windows:
                del self.windows["input"]
            if "inputborder" in self.windows:
                del self.windows["inputborder"]

            w = self.dimensions["input"] = {"height":1, "width":self.w-2, "top":self.h-3, "left":1}
            self.Spl["input_vertical"] = w["top"]
            self.Spl["input_horizontal"] = w["left"]
            bi = self.windows["inputborder"] = curses.newwin(w["height"]+2, w["width"]+2, w["top"]-1, w["left"]-1)
            bi.attron(self.colors["blue"] | curses.A_BOLD)
            bi.border()
            bi.noutrefresh()
            bi.attroff(self.colors["blue"] | curses.A_BOLD)
            self.windows["input"] = bi.subwin(w["height"], w["width"], w["top"], w["left"])
            self.windows["input"].attroff(self.colors["blue"] | curses.A_BOLD)
        except Exception as e:
            self.Help.Log("debug", "CreateEntryBox: " + str(e))
            ## Create curses parent window, get terminal size, draw windows
            # @param self Mucous (class)
            # @return line
    def Build(self):
        #       h, w = struct.unpack("HHHH", fcntl.ioctl(sys.stdout.fileno(),termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0)))[:2]
        #       os.environ["LINES"] = str(h)
        #       os.environ["COLUMNS"] =str(w)

        try:
            self.stdscr = curses.initscr()
            self.stdscr.erase()
            self.stdscr.refresh()
            ## @var h
            # Height of terminal / curses screen
            ## @var w
            # Width of terminal / curses screen
            self.h, self.w = self.stdscr.getmaxyx()

            self.CreateEntryBox()

            self.ModeTopbar()

            self.PopupMenu.show  = False
        except Exception as e:
            self.Help.Log("debug", "Build: " + str(e))
        try:
            if self.mode == "chat":
                self.ChatRooms.Mode()
            elif self.mode == "private":
                self.PrivateChat.Mode()
            elif self.mode == "browse":
                self.BrowseShares.Mode()
            elif self.mode == "transfer":
                self.Transfers.ModeTransfers()
            elif self.mode == "info":
                self.UserInfo.Mode()
            elif self.mode == "search":
                self.Search.Mode()
            elif self.mode == "lists":
                self.UsersLists.ModeLists()
            elif self.mode == "roomlist":
                self.RoomsList.Mode()
            elif self.mode == "setup":
                self.Setup.Default()
            elif self.mode in ("debug", "help"):
                self.Help.Mode()

        except Exception as e:
            self.Help.Log("debug", "Build part 2: " + str(e))
            curses.doupdate()
        try:


            self.stdscr.nodelay(1)
            self.edit.SelectEntryBox(self.windows["input"])
        except Exception as e:
            self.Help.Log("debug", "Build: " + str(e))
        return self.line

    ## Connect to Museekd if not connected
    # @param self Mucous (Class)
    def ManuallyConnect(self):
        try:
            if self.Spl["connected"] == 0:
                self.invalidpass = False
                self.line = ""
                self.edit.reset()
                self.D.connect()

                return 0
            else:
                self.Help.Log("status", "Already connected... aborting connection attempt.")
        except Exception as e:
            self.Help.Log("debug", "ManuallyConnect: " + str(e))

    ## Close mucous after disconnecting from museekd
    # @param self Mucous (Class)
    # @param error message to be displayed in the help log
    def shutdown(self, error=None):
        if error is not None:
            self.Help.Mode()
            self.Help.Log("status", "Shutting Down Mucous.. " +str(error) )
            sleep(1)
        try:
            self.timers["timeout"].cancel()
            self.timers["nick"].cancel()
            self.ChatRooms.ticker_timer.cancel()
            self.Muscan.timer.cancel()
            self.timers["retry"].cancel()
            self.timers["clear"].cancel()
            for timer in self.timers:
                timer.cancel()
        except Exception as e:
            self.Help.Log("debug", "shutdown: " + str(e))
        try:
            self.disconnect()
            # Quit
        except Exception as e:
            self.Help.Log("debug", "shutdown: " + str(e))

        self.stdscr.keypad(0)
        curses.nocbreak()
        curses.echo()
        curses.endwin()

        #os._exit(0)

    ## Disconnect from museekd
    # @param self Mucous (class)
    def disconnect(self):

        try:
            if self.Spl["connected"] == 1:
                #driver.Driver.close(self.D)
                self.D.close()
        except Exception as e:
            self.Help.Log("debug", "disconnect: " + str(e))



    ## Toggle the logging of chat messages to disk
    # @param self Mucous (class)
    def ToggleLogging(self):
        try:
            if "logging" in self.Config["mucous"]:
                if str(self.Config["mucous"]["logging"]) not in ("yes", "no"):
                    self.Config["mucous"]["logging"] = "yes"
                else:
                    if str(self.Config["mucous"]["logging"]) == "yes":
                        self.Config["mucous"]["logging"] = "no"
                    else:
                        self.Config["mucous"]["logging"] = "yes"
            else:
                if str(self.Config["mucous"]["logging"]) == "yes":
                    self.Config["mucous"]["logging"] = "no"
                else:
                    self.Config["mucous"]["logging"] = "yes"

            if str(self.Config["mucous"]["logging"]) == "yes":
                self.Help.Log("status", "Logging Chat is now Enabled.")
            else:
                self.Help.Log("status", "Logging Chat is now Disabled.")
        except Exception as e:
            self.Help.Log("debug", "ToggleLogging: " + str(e))

    ## Toggle alerts making beeps
    # @param self Mucous (class)
    def ToggleBeep(self):
        try:
            if str(self.Config["mucous"]["beep"]) == "yes":
                self.Config["mucous"]["beep"] = "no"
            else:
                self.Config["mucous"]["beep"] = "yes"
            if self.mode=="setup":
                self.Setup.Mode()
        except Exception as e:
            self.Help.Log("debug", "ToggleBeep: "+str(e))

    ## Toggle Away Status
    # @param self Mucous (class)
    def ToggleAwayStatus(self):
        try:
            if self.Spl["status"] == 0:
                self.D.SetStatus(1)
            elif self.Spl["status"] == 1:
                self.D.SetStatus(0)
        except Exception as e:
            self.Help.Log("debug", "ToggleAwayStatus: " +str( e) )
            ## Display Mucous version and away status in the terminal title, if possible
            # :: May cause display corruption
            # @param self Mucous (class)
    def TerminalTitle(self):
        # Changes Terminal's Title when Away Status changes
        try:
            if os.path.expandvars("$SHELL") in  ("/bin/bash", "/bin/sh"):
                if str(curses.termname() ) != "linux":
                    os.system("echo -ne \"\033]0;Mucous %s: %s\007\" " %(self.Version, self.logs["onlinestatus"] ))
        except Exception as e:
            self.Help.Log("debug", "TerminalTitle: " +str( e) )

    ## Emit pcspeaker style beep, if enabled
    # @param self Mucous (class)
    def Beep(self):
        try:
            if str(self.Config["mucous"]["beep"]) == "yes":
                if os.path.expandvars("$SHELL") in  ("/bin/bash", "/bin/sh"):
                    os.system("echo -ne \\\\a " )
        except Exception as e:
            self.Help.Log("debug", "beep: " + str(e))

    ## Redraw windows if user is in the current mode :: called on peer status updates
    # @param self Mucous (class)
    # @param user Username
    def ModeReload(self, user):

        if self.mode == "private":
            if user in self.PrivateChat.logs.keys():
                self.PrivateChat.Mode()
        elif self.mode == "chat":
            if user in self.ChatRooms.rooms[self.ChatRooms.current]:
                self.ChatRooms.Mode()
        elif self.mode == "info":
            if user in self.UserInfo.users:
                self.UserInfo.Mode()
        elif self.mode == "lists":
            if self.UsersLists.current in self.config.keys():
                if user in self.config[self.UsersLists.current].keys():
                    self.UsersLists.ModeLists()
        elif self.mode == "browse":
            if user in self.BrowseShares.users:
                self.BrowseShares.Mode()
        elif self.mode == "search":
            if user in self.Search.tickets.keys():
                self.Search.Mode()
        elif self.mode == "transfers":
            self.Transfers.ModeTransfers()
        elif self.mode == "roomlist":
            self.RoomsList.Mode()
        elif self.mode == "setup":
            self.Setup.Default()
        elif self.mode in ("help", "debug", "status"):
            self.Help.Mode()


    ## Add new/replace old keys in Mucous.config
    # @param self Mucous (class)
    # @param changetype type of change (Ex: buddy, unignore)
    # @param username the username of user being modified
    # @param value comment
    def ModifyConfig(self, changetype, username, value):
        try:

            username = self.dlang(username)
            if changetype == "buddy":
                if not self.config.has_key("buddies") or username not in self.config["buddies"].keys():
                    self.D.ConfigSet("buddies", username, "buddied by mucous")

            elif changetype == "unbuddy":
                if self.config.has_key("buddies") and username in self.config["buddies"].keys():
                    self.D.ConfigRemove("buddies", username)
                else:
                    self.Help.Log("status", "User not in buddy list: %s" % username)
            elif changetype == "ban":
                if not self.config.has_key("banned") or username not in self.config["banned"].keys():
                    self.D.ConfigSet("banned", username, "banned by mucous")
            elif changetype == "trusted":
                if not self.config.has_key("trusted") or username not in self.config["trusted"].keys():
                    self.D.ConfigSet("trusted", username, "")
            elif changetype == "unban":
                if self.config.has_key("banned") and username in self.config["banned"].keys():
                    self.D.ConfigRemove("banned", username)
                else:
                    self.Help.Log("status", "User not in ban list: %s" % username)
            elif changetype == "ignore":
                if not self.config.has_key("ignored") or username not in self.config["ignored"].keys():
                    self.D.ConfigSet("ignored", username, "")
                    self.Help.Log("status", "Ignored: %s" % username)
            elif changetype == "unignore":
                if self.config.has_key("ignored") and username in self.config["ignored"].keys():
                    self.D.ConfigRemove("ignored", username)
                else:
                    self.Help.Log("status", "User not in ignore list: %s" % username)
            elif changetype == "autojoin":
                room = username
                if not self.config.has_key("autojoin") or room not in self.config["autojoin"].keys():
                    self.D.ConfigSet("autojoin", room, "")
                else:
                    self.D.ConfigRemove("autojoin", room)

            elif changetype == "unautojoin":
                room = username
                if room in self.config["autojoin"].keys():
                    self.D.ConfigRemove("autojoin", room)
                else:
                    self.D.ConfigSet("autojoin", room, "")
            elif changetype == "trust":
                if not self.config.has_key("trusted") or username not in self.config["trusted"].keys():
                    self.D.ConfigSet("trusted", username,  "")
            elif changetype == "distrust":
                if self.config.has_key("trusted") and username in self.config["trusted"].keys():
                    self.D.ConfigRemove("trusted", username)
        except Exception as e:
            self.Help.Log("debug", "ModifyConfig: " + str(e))

    ## Update windows if a config change effects them
    # @param self Mucous (class)
    # @param domain which domain the config change was in
    def ConfigUpdateDisplay(self, domain):
        try:
            if domain in ("buddies", "banned", "trusted", "ignored",  "autojoin", "trusted"):
                if self.mode == "lists":
                    self.UsersLists.ModeLists()
                elif self.mode == "chat" :
                    self.ChatRooms.DrawBox()

                if self.PopupMenu.show == True:
                    self.PopupMenu.Draw()

            elif domain in ("interests.like", "interests.hate"):
                if self.mode == "lists" and self.UsersLists.current == "interests":
                    self.Recommendations.ModeInterests()
            elif domain in ("clients", "transfers", "server", "interfaces", "interfaces.bind", "userinfo") and self.mode == "setup":
                self.Setup.Mode()
            elif domain in ("encoding.users", "encoding" ) and self.mode == "browse":
                self.BrowseShares.Mode()
            elif domain in ("encoding.users" ) and self.mode == "private":
                self.PrivateChat.Mode()
            elif domain in ("encoding.rooms" ) and self.mode == "chat":
                self.ChatRooms.Mode()
        except Exception as e:
            self.Help.Log("debug", "ConfigUpdateDisplay: " + str(e))


    ## Autobuddy a user you're downloading from
    # :: Valid if self.Config["mucous"]["autobuddy"] is True
    # @param self Mucous (Class)
    # @param user Username
    def AutobuddyUser(self, user):
        if user == None:
            return
        if self.Config["mucous"]["autobuddy"]  != "yes":
            return
        if not self.config["buddies"].has_key(user):
            self.D.ConfigSet("buddies", user, "buddied by mucous")
            self.Help.Log("status", "Auto-Buddied: %s" % user)


    ## Append list of users in room to status (help mode) log
    # @param self Mucous (Class)
    # @param room Room Name
    def show_nick_list(self, room):
        try:
            ## @var colorednicks
            # display names in status log
            self.colorednicks = {}

            if self.ChatRooms.rooms[room] == None:
                return

            self.colorednicks[room] = []
            alphanicks=[]
            alphanicks = self.ChatRooms.rooms[room]
            alphanicks.sort(key=str.lower)
            self.Help.Log("status", "Users in " + room)
            for username in alphanicks:
                if username == self.username:
                    self.colorednicks[room].append([username, "Me"])
                elif username not in self.ChatRooms.rooms[room]:
                    self.colorednicks[room].append([username, "Left"])
                elif username in self.config["banned"]:
                    self.colorednicks[room].append([username, "Banned"])
                elif username in self.config["buddies"]:
                    self.colorednicks[room].append([username, "Buddies" ])
                else:
                    self.colorednicks[room].append([username, "Normal"])
                    self.colorednicks[room].append([" ["+str(self.user["statistics"][username])+"]", "Normal"])
                    line = username + (" " * (30 - len(username)) ) + "Files: " + str(self.user["statistics"][username][2])

                #line = "%s": [%s] Files" % (username,  )
                self.Help.Log("status", line)
                if username is not alphanicks[-1]:
                    self.colorednicks[room].append([", ", "NotLast"])
                    mtype = "List"
                    user = "!!!!"
                    msg = self.colorednicks[room]

            #self.ChatRooms.AppendChat("List", room, '!!!!', msg)
        except Exception as e:
            self.Help.Log("debug", "show_nick_list: " + str(e))



    ## Redraw windows for current mode
    # @param self is Mucous (Class)
    def refresh_windows(self):

        try:
            if self.mode =="transfer":
                if self.Config["mucous"]["transbox"]=="split":

                    self.Transfers.windows["border"]["uploads"].redrawwin()
                    self.Transfers.windows["border"]["uploads"].refresh()
                    self.Transfers.windows["border"]["downloads"].redrawwin()
                    self.Transfers.windows["border"]["downloads"].refresh()
                else:
                    if self.Transfers.current == "downloads":
                        self.Transfers.windows["border"]["downloads"].redrawwin()
                        self.Transfers.windows["border"]["downloads"].refresh()
                    elif self.Transfers.current == "uploads":
                        self.Transfers.windows["border"]["uploads"].redrawwin()
                        self.Transfers.windows["border"]["uploads"].refresh()
            elif self.mode == "lists":
                self.UsersLists.windows["border"][self.UsersLists.current].redrawwin()
                self.UsersLists.windows["border"][self.UsersLists.current].refresh()
                self.UsersLists.windows["text"][self.UsersLists.current].redrawwin()
                self.UsersLists.windows["text"][self.UsersLists.current].refresh()
            elif self.mode == "chat":
                self.ChatRooms.windows["border"]["chat"].redrawwin()
                self.ChatRooms.windows["border"]["chat"].refresh()
                self.ChatRooms.windows["text"]["chat"].redrawwin()
                self.ChatRooms.windows["text"]["chat"].refresh()
                if self.ChatRooms.shape not in ("chat-only",  "nostatuslog"):
                    if "roomstatus" in self.ChatRooms.windows["border"]:
                        self.ChatRooms.windows["border"]["roomstatus"].redrawwin()
                        self.ChatRooms.windows["border"]["roomstatus"].refresh()
                    if "roomstatus" in self.ChatRooms.windows["text"]:
                        self.ChatRooms.windows["text"]["roomstatus"].redrawwin()
                        self.ChatRooms.windows["text"]["roomstatus"].refresh()
                if self.ChatRooms.shape not in ( "noroombox", "chat-only"):
                    self.ChatRooms.windows["border"]["roombox"].redrawwin()
                    self.ChatRooms.windows["border"]["roombox"].refresh()
            elif self.mode == "search":
                #self.BrowseShares.DrawBrowseWin()
                self.Search.FormatResults(self.Search.current)
                curses.doupdate()
            elif self.mode == "browse":
                self.BrowseShares.DrawBrowseWin()
                self.BrowseShares.FormatBrowse()
                curses.doupdate()
            elif self.mode == "setup":
                self.Setup.Mode()
            elif self.mode == "info":
                self.UserInfo.Mode()
            else:
                pass
            self.windows["inputborder"].redrawwin()
            self.windows["inputborder"].refresh()
            self.ModeTopbar()
        except Exception as e:
            self.Help.Log("debug", "Refresh Windows: "+str(e))



    ## NewPlaying parser for InfoPipe or custom command
    # @param self is Mucous (Class)
    def NowPlaying(self):
        try:
            m = self.Config["mucous"]
            if "now-playing" not in m.keys():
                return
            if m["now-playing"] == "default":
                p = "/tmp/xmms-info"
                if os.path.exists(p):
                    fsock = open(p)
                    for i in range(3):  s = fsock.readline()[8:-1]
                    for i in range(10):  e = fsock.readline()[7:-1]
                    if "now-playing-prefix" in m.keys():
                        if m["now-playing-prefix"] != 'None' and m["now-playing-prefix"] != None:
                            message = ("%s %s") %(m["now-playing-prefix"], e)
                        else:
                            message ="Now %s: %s " % (s, e)
                    else:
                        message ="Now %s: %s " % (s, e)
                        fsock.close()
                    if self.mode == "chat":
                        self.ChatRooms.SayInChat( self.ChatRooms.current, message)
                    elif self.mode == "private":
                        self.PrivateChat.Send(self.PrivateChat.current, message)
                else: self.Help.Log("status", "WARNING: XMMS or BMP isn't running or the InfoPipe plugin isn't enabled")
            else:
                p = m["now-playing"]
                nowplaying = commands.getoutput(p).split('\n')
                nowplaying = nowplaying[0]
                if m["now-playing-prefix"] != None and m["now-playing-prefix"] != 'None':
                    message = "%s %s" % (m["now-playing-prefix"], nowplaying)
                    if self.mode == "chat" and self.ChatRooms.current != None:
                        self.ChatRooms.SayInChat( self.ChatRooms.current, message)

                    elif self.mode == "private" and self.PrivateChat.current != None:
                        self.PrivateChat.Send(self.PrivateChat.current, message )
                else:
                    message = nowplaying
                    if self.mode == "chat" and self.ChatRooms.current != None:
                        self.ChatRooms.SayInChat( self.ChatRooms.current, message)

                    elif self.mode == "private" and self.PrivateChat.current != None:
                        self.PrivateChat.Send(self.PrivateChat.current, message )
        except Exception as e:
            self.Help.Log("debug", "NowPlaying " +str(e))

    ## Remove control characters and attempt to encoding/decode string
    # @param self Mucous (class)
    # @param string the string
    # @return string
    def dlang(self, string):
        try:
            string1 = string.decode(self.Config["mucous"]["language"], "replace")
            string1 = string1.encode(self.Config["mucous"]["language"], "replace")
            string1 = string1.encode(self.Config["mucous"]["language"], "replace")
            try:
                z = ""

                for s in string1:
                    if s not in ("\n", chr(10)) and  curses.ascii.isctrl(s):
                        z += curses.ascii.unctrl(s)
                    else:
                        z += s
                return z
            except:
                return string1
        except Exception as e:
            return string


    ## One attempt at decoding string
    # @param self Mucous (class)
    # @param string a string
    # @return string
    def dencode_language(self, string):
        try:
            string = string.decode(self.Config["mucous"]["language"]).decode(self.Config["mucous"]["language"]).encode(self.Config["mucous"]["language"])
        except:
            pass
        return string

    ## One attempt at encoding string
    # @param self Mucous (class)
    # @param string a string
    # @return string
    def encode_language(self, string):
        try:
            string = string.encode(self.Config["mucous"]["language"])
        except:
            pass
        return string

    ## Set Input line's title
    # @param self Mucous (class)
    # @param title string
    def SetEditTitle(self, title, selected=True):
        try:
            if title != None:
                self.Spl["title"]= title
            else:
                self.Spl["title"] = "Join a room or something."
                ibw = self.windows["inputborder"]
                itw = self.windows["input"]
                ibw.erase()
            if selected:
                attribute = self.colors["blue"] | curses.A_BOLD
            else:
                attribute = self.colors["normal"] | curses.A_BOLD
                ibw.attroff(self.colors["blue"] | curses.A_BOLD)
                ibw.attron(attribute)
                ibw.border()
                #ibw.attroff(self.colors["blue"])

            if self.Spl["title"]:
                current = self.dlang(self.Spl["title"])
                if selected:
                    attribute = self.colors["cyan"] | curses.A_BOLD
                else:
                    attribute = self.colors["normal"] | curses.A_BOLD
                    ibw.addstr(0, 2, "< ")
                    ibw.addstr(0, 4, current[:self.w-8], attribute)
                    ibw.addstr(0, 4+len(current[:self.w-8]), " >")
                    itw.redrawwin()
                    itw.noutrefresh()
                    ibw.noutrefresh()


        except Exception as e:
            self.Help.Log("debug", "SetEditTitle: " + str(e))

    ## Draw Buttons for switching with the mouse to Instructions view
    # @param self Mucous (class)
    def DrawInstructionsButtons(self):
        try:
            if self.mode == "browse":
                gi = "Instructions"
                w = self.BrowseShares.dimensions["browse"]
            elif self.mode == "info":
                gi = "Instructions"
                w = self.UserInfo.dimensions["info"]


            pos = w["width"]-3-len(gi)
            if self.mode != "lists":

                if self.mode == "browse":
                    mw = self.BrowseShares.windows["border"]
                elif self.mode == "info":
                    mw = self.UserInfo.windows["border"]
                else:
                    mw = self.windows["border"][ self.mode ]
            else:
                mw = self.windows["border"][ self.UsersLists.current ]
                mw.addstr(0,pos, "< ")
                mw.addstr(0,pos+2, gi, self.colors["cyan"] | curses.A_BOLD)
                mw.addstr(0,pos+2+len(gi), " >")
                vertex = w["height"]+1

            if self.mode == "browse":
                blah = None
                if "encoding.users" in self.config:
                    if self.BrowseShares.current in self.config["encoding.users"]:
                        blah = self.config["encoding.users"][self.BrowseShares.current]
                    else:
                        blah = self.config["encoding"]["filesystem"]
                if blah != None:
                    mw.addstr(vertex,w["width"]-17-len(blah)-4, "<" + (" " *( len(blah) +2) )+  ">")
                    mw.addstr(vertex,w["width"]-17-len(blah)-2, blah, self.colors["cyan"] | curses.A_BOLD)
                    mw.addstr(vertex,w["width"]-11, "< ")
                    mw.addstr(vertex,w["width"]-9, "Close ", self.colors["cyan"] | curses.A_BOLD)
                    mw.addstr(vertex,w["width"]-3, ">")
            elif self.mode == "info":
                isw = self.UserInfo.windows["statsborder"]
                isw.addstr(vertex,3, "< ")
                isw.addstr(vertex,5, "Close ", self.colors["cyan"] | curses.A_BOLD)
                isw.addstr(vertex,11, ">")
                isw.noutrefresh()
                mw.noutrefresh()
        except Exception as e:
            self.Help.Log("debug", "DrawInstructionsButtons: " + str(e))

    ## Draw tabs from a list of strings
    # @param self Mucous (class)
    # @param tab_box_list list of strings
    # @param selected_tab current tab
    def DrawTabs(self, tab_box_list, selected_tab, selected=False):
        try:
            if tab_box_list == [None]:
                return
            lang = self.Config["mucous"]["language"]

            if "bar" in self.windows["tab"]:
                del self.windows["tab"]["bar"]
                tbar = self.windows["tab"]["bar"] = curses.newwin(3, self.w, 1, 0)
            if selected:
                attribute = self.colors["cyan"]
            else:
                attribute = self.colors["white"]

            tbar.hline(1, 1, curses.ACS_HLINE, self.w-2, attribute)
            self.activeitems["positions"]= {}
            tbar.addstr(1,0, "<", attribute)
            tbar.addstr(1,self.w-1, ">", attribute)

            tbar.noutrefresh()
            if tab_box_list == []:
                return
            pos = 1
            current = False
            if self.mode == "search":
                alpha_list = self.SortedDict()
                for keyname, keyvalue in self.Search.tickets.items():
                    alpha_list[keyname] = keyvalue
                    tab_box_list = alpha_list.keys()
            for string in tab_box_list:

                if self.mode == "search":
                    sting = self.Search.tickets[string][:13]
                    if string == self.Search.current:
                        current = True
                    else:
                        current = False
                else:
                    sting = string[:13]
                    if string == selected_tab:
                        current = True
                    else:
                        current = False

                move = len(sting)+2

                sting = self.dlang(sting)
                self.activeitems["positions"][string] = pos, move+pos

                if pos + move >= self.w -2:
                    return

                tb = curses.newwin(3, len(sting)+2, 1, pos)
                if current == True:
                    tb.attron(self.colors["green"])
                    tb.border()
                    tb.noutrefresh()
                    tl = tb.subwin(1,len(sting),2,pos+1)

                try:

                    if self.mode == "search":
                        if current:
                            tl.addstr(sting, self.colors["green"] | curses.A_BOLD)
                        else:
                            tl.addstr(sting, curses.A_BOLD)

                        continue

                    username = string
                    if current:
                        if string in self.user["status"]:
                            attr = curses.A_BOLD
                            if self.user["status"][username] == 1: # Away
                                attr = self.colors["yellow"] | curses.A_BOLD
                            elif self.user["status"][username] == 2: # Online
                                attr = self.colors["green"] | curses.A_BOLD
                            elif self.user["status"][username] == 0: # Offline
                                attr = self.colors["red"] | curses.A_BOLD
                                tl.addstr(sting, attr)
                        else:
                            tl.addstr(sting, self.colors["red"] | curses.A_BOLD)
                    else:
                        if string in self.user["status"]:
                            attr = curses.A_NORMAL
                            if self.user["status"][username] == 1:
                                attr = self.colors["yellow"]
                            elif self.user["status"][username] == 2:
                                attr = self.colors["green"]
                            elif self.user["status"][username] == 0:
                                attr = self.colors["red"]
                                tl.addstr(sting, attr)
                        else:
                            tl.addstr(sting, self.colors["red"])

                except:
                    # Always get errors, because text is the same size as window
                    pass
                pos += len(sting)+2
                tl.noutrefresh()
                # Cleanup stale windows
                del tl
                del tb

        except Exception as e:
            self.Help.Log("debug", "DrawTabs: " + str(e))

    ## Draw the Online Status in Specific colors
    # @param self Mucous (class)
    def DrawOnlineStatus(self):
        try:
            osw = self.windows["border"]["onlinestatus"]

            if self.logs["onlinestatus"] == "Away":
                color = self.colors["blackyellow"]
                status = " " + self.logs["onlinestatus"]
            elif self.logs["onlinestatus"] == "Online":
                color = self.colors["blackgreen"]
                #color = self.colors["cyanyellow"]
                status = " " + self.logs["onlinestatus"]
            elif self.logs["onlinestatus"] == "Offline":
                color = self.colors["blackred"]
                status = self.logs["onlinestatus"]
            elif self.logs["onlinestatus"] == "Closed":
                color = self.colors["whitered"]
                status = " " + self.logs["onlinestatus"]
            else:
                color = self.colors["blackwhite"]
                status = self.logs["onlinestatus"]
                osw.bkgdset(" ", color)
                osw.erase()
                osw.addstr(status,  color )
                osw.refresh()
        except Exception as e :
            self.Help.Log("debug", "DrawOnlineStatus: " + str(e))

    ## Create and Draw the Topbar
    # @param self Mucous (class)
    def ModeTopbar(self):
        try:
            # Clean stale windows
            if "top" in self.windows["border"]:
                del self.windows["border"]["top"]
            if "onlinestatus" in self.windows["border"]:
                del self.windows["border"]["onlinestatus"]


            if "username" in self.windows["border"]:
                del self.windows["border"]["username"]


            tb = self.windows["border"]["top"] =   curses.newwin(1, self.w, 0, 0)
            tb.bkgdset(" ", self.colors["blackwhite"]  | curses.A_REVERSE | curses.A_BOLD)
            tb.idlok(1)
            tb.erase()
            tb.noutrefresh()

            osw = self.windows["border"]["onlinestatus"]  =  curses.newwin(1, 8, 0, 0)
            #osw.bkgdset(" ", self.colors["blackwhite"]  |curses.A_REVERSE | curses.A_BOLD)
            osw.idlok(1)
            self.DrawOnlineStatus()



            self.Search.Count(None)

            un = self.windows["border"]["username"] =  curses.newwin(1, 16, 0, 9)
            un.idlok(1)
            un.bkgdset(" ", self.colors["blackwhite"]  | curses.A_REVERSE | curses.A_BOLD)
            un.erase()
            if self.username != None:
                try:

                    un.addstr(self.dlang(self.username[:15]),  self.colors["blackwhite"] )
                except:
                    pass
                un.noutrefresh()

            self.Alerts.Mode()
            self.Transfers.Status()
        except Exception as e :
            self.Help.Log("debug", "topbar mode" + str(e))

    ## Create and draw the HotKeyBar (bottom of UI)
    # @param self Mucous (class)
    def HotKeyBar(self):
        try:
            # Clean stale windows
            if "bottom" in self.windows["border"]:
                del self.windows["border"]["bottom"]

            bb = self.windows["border"]["bottom"] = curses.newwin(1, self.w-1, self.h-1, 0)
            bb.addstr(" 1",  curses.A_BOLD)
            if self.mode == "chat":
                if self.Alerts.alert["CHAT"] != {}:
                    nick = 0
                    for room, status in self.Alerts.alert["CHAT"].items():
                        if status == "nick":
                            nick = 1
                    if nick == 1:
                        bb.addstr("Chat", self.colors["red"] |curses.A_BOLD |curses.A_REVERSE )
                    else:
                        bb.addstr("Chat", self.colors["yellow"] |curses.A_BOLD |curses.A_REVERSE )
                else:
                    bb.addstr("Chat",  curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["CHAT"] != {}:
                    nick = 0
                    for room, status in self.Alerts.alert["CHAT"].items():
                        if status == "nick":
                            nick = 1
                    if nick == 1:
                        bb.addstr("Chat", self.colors["red"] | curses.A_REVERSE )
                    else:
                        bb.addstr("Chat", self.colors["yellow"] | curses.A_REVERSE )
                else:
                    bb.addstr("Chat",  self.colors["cybg"])
                    bb.addstr(" 2",  curses.A_BOLD)
            if self.mode == "private":
                if self.Alerts.alert["PRIVATE"] != []:
                    bb.addstr("Private", self.colors["yellow"] |curses.A_BOLD |curses.A_REVERSE )
                else:
                    bb.addstr("Private",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["PRIVATE"] != []:
                    bb.addstr("Private", self.colors["yellow"] |curses.A_REVERSE )
                else:
                    bb.addstr("Private", self.colors["cybg"])
                    bb.addstr(" 3",   curses.A_BOLD)
            if self.mode == "transfer":
                bb.addstr("Transfers",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                bb.addstr("Transfers", self.colors["cybg"])

            bb.addstr(" 4",  curses.A_BOLD)
            if self.mode == "search":
                if self.Alerts.alert["SEARCH"] != []:
                    bb.addstr("Search", self.colors["yellow"] |curses.A_REVERSE |curses.A_BOLD)
                else:
                    bb.addstr("Search",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["SEARCH"] != []:
                    bb.addstr("Search", self.colors["yellow"] |curses.A_REVERSE )
                else:
                    bb.addstr("Search", self.colors["cybg"])
                    bb.addstr(" 5",  curses.A_BOLD)
            if self.mode == "info":
                if self.Alerts.alert["INFO"] != []:
                    bb.addstr("Info", self.colors["yellow"] |curses.A_REVERSE |curses.A_BOLD)
                else:
                    bb.addstr("Info",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["INFO"] != []:
                    bb.addstr("Info", self.colors["yellow"] |curses.A_REVERSE )
                else:
                    bb.addstr("Info", self.colors["cybg"])
                    bb.addstr(" 6",  curses.A_BOLD)
            if self.mode == "browse":
                if self.Alerts.alert["BROWSE"] != []:
                    bb.addstr("Browse", self.colors["yellow"] |curses.A_REVERSE |curses.A_BOLD)
                else:
                    bb.addstr("Browse",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["BROWSE"] != []:
                    bb.addstr("Browse", self.colors["yellow"] |curses.A_REVERSE)
                else:
                    bb.addstr("Browse", self.colors["cybg"])

            bb.addstr(" 7",  curses.A_BOLD)
            if self.mode == "lists":
                bb.addstr("Users",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                bb.addstr("Users",  self.colors["cybg"])

            bb.addstr(" 8",  curses.A_BOLD)
            if self.mode == "roomlist":
                bb.addstr("Rooms",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                bb.addstr("Rooms", self.colors["cybg"])

            bb.addstr(" 9",  curses.A_BOLD)
            if self.mode == "setup":
                bb.addstr("Setup",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                bb.addstr("Setup",  self.colors["cybg"])
                bb.addstr(" 10",  curses.A_BOLD)
            if self.mode in ("debug", "help", "status"):
                if self.Alerts.alert["HELP"] != []:
                    bb.addstr("Help", self.colors["yellow"] |curses.A_BOLD |curses.A_REVERSE )
                else:
                    bb.addstr("Help",curses.A_REVERSE |  self.colors["greenblack"])
            else:
                if self.Alerts.alert["HELP"] != []:
                    bb.addstr("Help", self.colors["yellow"] | curses.A_REVERSE )
                else:
                    bb.addstr("Help",  self.colors["cybg"])
        except:
            pass
        bb.noutrefresh()

    ## Save to log
    # @param self Mucous (class)
    # @param messagetype Type of message (Ex: private, room)
    # @param timestamp Timestamp of when message was recieved
    # @param place User's name for private chat; room name for chat rooms
    # @param message the message to be logged

    def FileLog(self, messagetype, timestamp, place, message):
        try:
            if '/' in place:
                place = place.replace("/", "\\")
                path = os.path.join(os.path.expanduser(self.Config["mucous"]["log_dir"]), messagetype, place)
                dir = os.path.split(path)[0]
            try:
                if not os.path.isdir(dir):
                    os.makedirs(dir)
                    f = open(path, "a")
                    ## replace inline newlines to preserve formatting
                message.replace("\n","\\n")
                f.write("%s %s\n" % (timestamp, message))
                f.close()
            except:
                self.Help.Log("status", "Cannot write to file %s, check permissions" % path)
        except Exception as e:
            self.Help.Log("debug", "FileLog: " + str(e))

    ## Check if we've recieved a username
    # @param self Mucous (class)
    def ThreadNickCheck(self):
        try:
            if self.username != None:
                return
            self.mode = "status"
            self.Help.Mode()
            self.Help.Log("status", "Connection is taking a while to start, maybe you are trying to connect to a FTP daemon?")
            self.Help.Log("status", "Killing connection..")
            self.Help.Log("status", "Try using /interface to connect to a different port.")
            for line in self.Help.log["connect"]:
                self.Help.Log("status", line)
            if self.D.socket is not None:
                self.D.close()
        except Exception as e:
            self.Help.Log("debug", "ThreadNickCheck: " + str(e))

    ## Automatically Retry failed downloads every 30 seconds
    # @param self Mucous (class)
    def ThreadTransfersRetry(self):
        try:
            if self.Config["mucous"]["auto-retry"] != "yes":
                self.timers["retry"].cancel()
            else:
                for user_path, transfer  in self.Transfers.transfers["downloads"].items():
                    if int(transfer[3]) in (11, 12, 13, 14):
                        self.D.DownloadFile(transfer[1], transfer[2])
                        self.timers["retry"].cancel()
                        self.timers["retry"] = threading.Timer(30.0, self.ThreadTransfersRetry)
                        self.timers["retry"].start()
        except Exception as e:
            self.Help.Log("debug", "ThreadTransfersRetry: " + str(e))

    ## Automatically Retry failed downloads every 30 seconds
    # @param self Mucous (class)
    def AwayTimeout(self):
        try:
            self.timers["timeout"].cancel()
            if self.Spl["status"] == 0:
                self.timedout = True
                self.ToggleAwayStatus()

        except Exception as e:
            self.Help.Log("debug", "AwayTimeout: " + str(e))

    ## Automatically Clear failed uploads and finished downloads every 30 seconds
    # @param self Mucous (class)
    def ThreadTransfersClear(self):
        try:
            if self.Config["mucous"]["auto-clear"] != "yes":
                self.timers["clear"].cancel()
            else:
                for userpath, values in self.Transfers.transfers["uploads"].items():
                    if values[3] in (0, 10, 11, 12, 13, 14):
                        self.D.TransferRemove(1, values[1], values[2])

                for userpath, values in self.Transfers.transfers["downloads"].items():
                    if values[3] == 0:
                        self.D.TransferRemove(0, values[1], values[2])
                        self.timers["clear"].cancel()

                self.timers["clear"] = threading.Timer(30.0, self.ThreadTransfersClear)
                self.timers["clear"].start()
        except Exception as e:
            self.Help.Log("debug", "ThreadTransfersClear: " + str(e))

try:
    import ctypes
    # Linux style
    libc = ctypes.CDLL('libc.so.6')
    libc.prctl(15, 'mucous', 0, 0, 0)
except:
        pass
try:
    if pcg:
        import pycallgraph
        pycallgraph.start_trace()

    if profile:
        import hotshot
        ## @var log
        # Profiler's log file (Ex: config.profile)
        log = os.path.expanduser(config_file) + ".profile"
        ## @var profiler
        # Hotshot profiler
        profiler = hotshot.Profile(log)
        print("Starting using the profiler (saving log to %s)" % log)
        sleep(1)
        profiler.runcall(Mucous)
    else:
        Mucous()
except Exception as e:
    curses.nocbreak()
    curses.noecho()
    curses.endwin()
    sys.stdout.flush()
    print(e)
else:
    e = ""
if pcg:
    pycallgraph.make_dot_graph('calltrace.png')



if debug:
    debug_log = open("mucous_debug.log", 'a')
    log = [e]
    tbe = sys.exc_info()
    ex = "BUG "
    for line in tbe:
        #if line is tbe[0]:
        log.append("TB: %s" % (line) )
        tb= traceback.extract_tb(sys.exc_info()[2])

    for line in tb:
        if type(line) is tuple:
            xline = ""
            for item in line:
                xline += str(item) + " "
                line = xline

        newline = ""
        for character in line:
            if curses.ascii.isctrl(character):
                character = curses.ascii.unctrl(character)
                newline += character
        if line is tb[0]:
            log.append( "%s%s" % (ex,newline))
        else:
            log.append( "%s%s" % (ex,newline))
    for line in log:
        debug_log.write(str(line)+"\n")
        debug_log.close()
        sys.exit()
