from time import sleep
import requests
from distutils.util import strtobool
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class HASS_API:
    def __init__(self, ip, port, key, url="/api", https=False, verify=True):

        if strtobool(https):
            self.api = "https://"
        else:
            self.api = "http://"

        self.api = self.api + str(ip) + ":" + str(port) + str(url)

        self.verify = strtobool(verify)

        self.header = {
            "Authorization": "Bearer {}".format(key),
            "content-type": "application/json",
        }

    def write(self, id: str):
        url = self.api + "/services/input_boolean/turn_on"
        data = {"entity_id": id}
        res = requests.post(url, json=data, headers=self.header, verify=self.verify)
        res.raise_for_status()

    def read(self, id: str) -> int:
        url = self.api + "/states/" + id
        res = requests.get(url, timeout=11, headers=self.header, verify=self.verify)
        res.raise_for_status()
        return int(float(res.json()["state"]))


class HASS_SESSION:
    def __init__(self, api: HASS_API, counter, session) -> None:
        self.api: HASS_API = api
        self._counter = counter
        self._session = session

    def end(self) -> bool:
        self.api.write(self._session)
        print("counter = {}".format(self.api.read(self._counter)))
        return not self.api.read(self._counter) > 0

    @property
    def counter(self) -> int:
        return self.api.read(self._counter)


if __name__ == "__main__":
    from os import path
    from configobj import ConfigObj

    config = ConfigObj(path.expandvars(r"config.ini"))
    ha = HASS_API(**config["HASS"])

    ha_session = HASS_SESSION(ha, **config["USERS"]["test"])
    while not ha_session.end():
        sleep(10)
        print("connected {}".format(ha_session.counter))

    if ha_session.end():
        print("logout")
