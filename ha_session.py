import win32service
import win32serviceutil
import win32api
import win32event
import sys
import socket
import servicemanager

from hass_api import *
from win32_session import *

from os import path
from configobj import ConfigObj


class Session:
    def __init__(self):
        self.run = True
        # self.connected = False
        self.config = ConfigObj(path.expandvars(r"%ProgramData%\ha_session\config.ini"))
        self.ha = HASS_API(**self.config["HASS"])
        self.error = 0
        self.old_user = dict()

    def loop(self, is_running):
        # print("isrunning = {}".format(is_running))
        for session in connected_user():
            user = session["UserName"]
            user_id = session["SessionId"]

            if user in self.config["USERS"].keys():

                if user_id not in self.old_user.keys():
                    self.old_user[user_id] = user  # on associe le user avec le userid
                    servicemanager.LogInfoMsg("login of {}".format(user))

                self.action(user, user_id)
            elif user_id in self.old_user.keys():  # le login a été changé
                self.config["USERS"].rename([self.old_user[user_id]], user)
                self.config.write()
                self.action(user, user_id)
            elif (
                user not in self.config["USERS"].keys()
                and user_id in self.old_user.keys()
            ):  # l'utilisateur c'est déconnecté
                servicemanager.LogInfoMsg("logout of {}".format(user))
                del self.old_user[user_id]

    def action(self, user, user_id):
        ret = 0
        # self.connected = True
        # while self.run and self.connected and is_running:
        ha_session = HASS_SESSION(api=self.ha, **self.config["USERS"][user])
        try:
            if ha_session.end():
                self.error = 0
                servicemanager.LogInfoMsg("forced logout of {}".format(user))
                close(user_id)
        except:
            self.error += 1
            servicemanager.LogInfoMsg("connection error n = {}".format(self.error))

        if self.error > 60:
            self.error = 0
            # self.connected = False
            servicemanager.LogInfoMsg(
                "connection error forced logout of {}".format(user)
            )
            close(user_id)

    def stop(self):
        self.run = False


class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "ha_session"
    _svc_display_name_ = "HA Session"
    _svc_description_ = "control parantal pour Homme Assistant"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, *args)
        self.log("Service Initialized.")
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def log(self, msg):
        servicemanager.LogInfoMsg(str(msg))

    def sleep(self, sec):
        win32api.Sleep(sec * 1000, True)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop()
        self.log("Service has stopped.")
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        self.start()
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.log("Service is starting.")
            self.main()
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
        except Exception as e:
            s = str(e)
            self.log("Exception :" + s)
            self.SvcStop()

    def start(self):
        print("start")
        self.isrunning = True
        self.session = Session()
        pass

    def stop(self):
        print("stop")
        self.isrunning = False
        # try:
        #     # logic
        #     pass
        # except Exception as e:
        #     self.log(str(e))

    def main(self):
        print("main")
        self.isrunning = True
        rc = 1
        while self.isrunning:
            # Check to see if self.hWaitStop happened
            if rc == win32event.WAIT_OBJECT_0:
                self.log("Service has stopped")
                break
            else:
                try:
                    # logic
                    self.session.loop(self.isrunning)
                    # self.sleep(30)
                    pass
                except Exception as e:
                    self.log(str(e))

            rc = win32event.WaitForSingleObject(self.stop_event, 1 * 1000)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(Service)
