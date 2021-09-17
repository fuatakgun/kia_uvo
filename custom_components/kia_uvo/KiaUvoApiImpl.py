import logging

from datetime import datetime
from datetime import tzinfo
import push_receiver
import random
import requests
import uuid
from urllib.parse import parse_qs, urlparse

from homeassistant.util import dt as dt_util

from .const import *
from .Token import Token

_LOGGER = logging.getLogger(__name__)


class KiaUvoApiImpl:
    def __init__(
        self,
        username: str,
        password: str,
        pin: int,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
    ):
        self.username = username
        self.password = password
        self.pin = pin
        self.use_email_with_geocode_api = use_email_with_geocode_api
        self.stamps = None
        self.region = region
        self.brand = brand


    def login(self) -> Token:
        pass

    def get_cached_vehicle_status(self, token: Token):
        pass

    def get_geocoded_location(self, lat, lon):
        email_parameter = ""
        if self.use_email_with_geocode_api == True:
            email_parameter = "&email=" + self.username

        url = (
            "https://nominatim.openstreetmap.org/reverse?lat="
            + str(lat)
            + "&lon="
            + str(lon)
            + "&format=json&addressdetails=1&zoom=18"
            + email_parameter
        )
        response = requests.get(url)
        response = response.json()
        return response

    def update_vehicle_status(self, token: Token):
        pass

    def lock_action(self, token: Token, action):
        pass

    def start_climate(self, token: Token):
        pass

    def stop_climate(self, token: Token):
        pass

    def start_charge(self, token: Token):
        pass

    def stop_charge(self, token: Token):
        pass

    def get_timezone_by_region(self) -> tzinfo:
        if REGIONS[self.region] == REGION_CANADA:
            return dt_util.DEFAULT_TIME_ZONE
        elif REGIONS[self.region] == REGION_EUROPE:
            return TIME_ZONE_EUROPE
