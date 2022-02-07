import win32service
import win32serviceutil
import win32api
import win32event
import subprocess
import sys
import socket
import servicemanager

import requests
from os import path
from configobj import ConfigObj

import win32ts

from win32com.shell import shell

protocols = {
    win32ts.WTS_PROTOCOL_TYPE_CONSOLE: "console",
    win32ts.WTS_PROTOCOL_TYPE_ICA: "citrix",
    win32ts.WTS_PROTOCOL_TYPE_RDP: "rdp",
}


def close(id):
    """fermer la seesion"""
    # ctypes.windll.user32.ExitWindowsEx(0, 1)
    # print("logoff {}".format(id))
    servicemanager.LogInfoMsg("logoff {}".format(id))
    subprocess.call(["logoff", str(id)])


def connected_user():
    # out = subprocess.check_output("quser", text=True, encoding="utf16")
    hServer = win32ts.WTS_CURRENT_SERVER_HANDLE
    for session in win32ts.WTSEnumerateSessions(hServer):
        sessionId = session["SessionId"]
        session["UserName"] = win32ts.WTSQuerySessionInformation(
            hServer, sessionId, win32ts.WTSUserName)
        session[
            "WinStationName"] = session["WinStationName"] or "(disconnected)"
        session["Protocol"] = win32ts.WTSQuerySessionInformation(
            hServer, sessionId, win32ts.WTSClientProtocolType)
        session["ProtocolName"] = protocols.get(session["Protocol"], "unknown")

        # print(session)
        yield session


class HASS_API:
    def __init__(self, ip, port, key, url="/api", https=False):

        if https:
            self.api = "https://"
        else:
            self.api = "http://"

        self.api = self.api + str(ip) + ":" + str(port) + str(url)

        self.header = {
            "Authorization": "Bearer {}".format(key),
            "content-type": "application/json",
        }

    def write(self, id: str):
        url = self.api + "/services/input_boolean/turn_on"
        data = {"entity_id": id}
        res = requests.post(url, json=data, headers=self.header)
        res.raise_for_status()

    def read(self, id: str) -> int:
        url = self.api + "/states/" + id
        res = requests.get(url, timeout=11, headers=self.header)
        res.raise_for_status()
        return int(float(res.json()["state"]))


class Session:
    def __init__(self):
        self.run = True
        # self.connected = False
        self.config = ConfigObj(
            path.expandvars(r"%ProgramData%\ha_session\config.ini"))
        self.ha = HASS_API(**self.config["HASS"])
        self.error = 0
        self.old_user = dict()

    def loop(self, is_running):
        # print("isrunning = {}".format(is_running))
        for session in connected_user():
            user = session["UserName"]
            user_id = session["SessionId"]
            if (session["WinStationName"] !=
                    "Console"):  # si l'utilisateur est un service
                continue

            print(session)
            if user in self.config["USERS"].keys():

                if user_id not in self.old_user.keys():
                    self.old_user[
                        user_id] = user  # on associe le user avec le userid
                    servicemanager.LogInfoMsg("login of {}".format(user))

                self.action(user, user_id)
            elif user_id in self.old_user.keys():  # le login a été changé
                self.config["USERS"].rename([self.old_user[user_id]], user)
                self.config.write()
                self.action(user, user_id)
            elif (user not in self.config["USERS"].keys() and user_id
                  in self.old_user.keys()):  # l'utilisateur c'est déconnecté
                servicemanager.LogInfoMsg("logout of {}".format(user))
                del self.old_user[user_id]

    def action(self, user, user_id):
        ret = 0
        # self.connected = True
        # while self.run and self.connected and is_running:
        try:
            ret = self.ha.read(self.config["USERS"][user]["counter"])
            print(ret)
        except:
            self.error += 1
            servicemanager.LogInfoMsg("connection error n = {}".format(
                self.error))
        else:
            self.error = 0
            if ret == 0:
                # self.connected = False
                close(user_id)

        if self.error > 10:
            self.error = 0
            # self.connected = False
            servicemanager.LogInfoMsg("forced logout of {}".format(user))
            close(user_id)

        self.ha.write(self.config["USERS"][user]["session"])

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
            win32event.WaitForSingleObject(self.stop_event,
                                           win32event.INFINITE)
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
