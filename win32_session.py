import subprocess
from time import sleep
import win32ts


protocols = {
    win32ts.WTS_PROTOCOL_TYPE_CONSOLE: "console",
    win32ts.WTS_PROTOCOL_TYPE_ICA: "citrix",
    win32ts.WTS_PROTOCOL_TYPE_RDP: "rdp",
}


def close(id):
    """fermer la seesion"""
    # ctypes.windll.user32.ExitWindowsEx(0, 1)
    # print("logoff {}".format(id))
    # servicemanager.LogInfoMsg("logoff {}".format(id))
    subprocess.call(["logoff", str(id)])


def connected_user():
    # out = subprocess.check_output("quser", text=True, encoding="utf16")
    hServer = win32ts.WTS_CURRENT_SERVER_HANDLE
    for session in win32ts.WTSEnumerateSessions(hServer):
        sessionId = session["SessionId"]
        session["UserName"] = win32ts.WTSQuerySessionInformation(
            hServer, sessionId, win32ts.WTSUserName
        )
        session["WinStationName"] = session["WinStationName"] or "(disconnected)"
        # session["Protocol"] = win32ts.WTSQuerySessionInformation(
        #    hServer, sessionId, win32ts.WTSClientProtocolType
        # )
        # session["ProtocolName"] = protocols.get(session["Protocol"], "unknown")

        # print(session)
        if session["WinStationName"] == "Console":
            yield session


if __name__ == "__main__":
    for user in connected_user():
        print("disconnect user {} in 30s".format(user))
        sleep(30)
        close(user["SessionId"])
