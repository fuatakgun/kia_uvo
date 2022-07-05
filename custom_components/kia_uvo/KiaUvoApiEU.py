from datetime import datetime, timedelta
import json
import logging
import random
import traceback
from urllib.parse import parse_qs, urlparse
import uuid

from bs4 import BeautifulSoup
import dateutil.parser
import push_receiver
import pytz
import requests

from .KiaUvoApiImpl import KiaUvoApiImpl
from .Token import Token
from .const import BRAND_HYUNDAI, BRAND_KIA, BRANDS, DATE_FORMAT, DOMAIN

_LOGGER = logging.getLogger(__name__)

INVALID_STAMP_RETRY_COUNT = 1
USER_AGENT_OK_HTTP: str = "okhttp/3.10.0"
USER_AGENT_MOZILLA: str = "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
ACCEPT_HEADER_ALL: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"


class KiaUvoApiEU(KiaUvoApiImpl):
    def __init__(
        self,
        username: str,
        password: str,
        region: int,
        brand: int,
        use_email_with_geocode_api: bool = False,
        pin: str = "",
    ):
        super().__init__(
            username, password, region, brand, use_email_with_geocode_api, pin
        )

        if BRANDS[brand] == BRAND_KIA:
            self.BASE_DOMAIN: str = "prd.eu-ccapi.kia.com"
            self.CCSP_SERVICE_ID: str = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
            self.APP_ID: str = "e7bcd186-a5fd-410d-92cb-6876a42288bd"
            self.BASIC_AUTHORIZATION: str = (
                "Basic ZmRjODVjMDAtMGEyZi00YzY0LWJjYjQtMmNmYjE1MDA3MzBhOnNlY3JldA=="
            )
            self.LOGIN_FORM_HOST = "eu-account.kia.com"
        elif BRANDS[brand] == BRAND_HYUNDAI:
            self.BASE_DOMAIN: str = "prd.eu-ccapi.hyundai.com"
            self.CCSP_SERVICE_ID: str = "6d477c38-3ca4-4cf3-9557-2a1929a94654"
            self.APP_ID: str = "014d2225-8495-4735-812d-2616334fd15d"
            self.BASIC_AUTHORIZATION: str = "Basic NmQ0NzdjMzgtM2NhNC00Y2YzLTk1NTctMmExOTI5YTk0NjU0OktVeTQ5WHhQekxwTHVvSzB4aEJDNzdXNlZYaG10UVI5aVFobUlGampvWTRJcHhzVg=="
            self.LOGIN_FORM_HOST = "eu-account.hyundai.com"

        self.BASE_URL: str = self.BASE_DOMAIN + ":8080"
        self.USER_API_URL: str = "https://" + self.BASE_URL + "/api/v1/user/"
        self.SPA_API_URL: str = "https://" + self.BASE_URL + "/api/v1/spa/"
        self.CLIENT_ID: str = self.CCSP_SERVICE_ID
        self.GCM_SENDER_ID = 199360397125

        if BRANDS[brand] == BRAND_KIA:
            auth_client_id = "f4d531c7-1043-444d-b09a-ad24bd913dd4"
            self.LOGIN_FORM_URL: str = (
                "https://"
                + self.LOGIN_FORM_HOST
                + "/auth/realms/eukiaidm/protocol/openid-connect/auth?client_id="
                + auth_client_id
                + "&scope=openid%20profile%20email%20phone&response_type=code&hkid_session_reset=true&redirect_uri="
                + self.USER_API_URL
                + "integration/redirect/login&ui_locales=en&state=$service_id:$user_id"
            )
        elif BRANDS[brand] == BRAND_HYUNDAI:
            auth_client_id = "64621b96-0f0d-11ec-82a8-0242ac130003"
            self.LOGIN_FORM_URL: str = (
                "https://"
                + self.LOGIN_FORM_HOST
                + "/auth/realms/euhyundaiidm/protocol/openid-connect/auth?client_id="
                + auth_client_id
                + "&scope=openid%20profile%20email%20phone&response_type=code&hkid_session_reset=true&redirect_uri="
                + self.USER_API_URL
                + "integration/redirect/login&ui_locales=en&state=$service_id:$user_id"
            )

        self.stamps_url: str = (
            "https://raw.githubusercontent.com/neoPix/bluelinky-stamps/master/"
            + BRANDS[brand].lower()
            + "-"
            + self.APP_ID
            + ".v2.json"
        )

    def get_stamps_from_bluelinky(self) -> list:
        stamps = []
        response = requests.get(self.stamps_url)
        stamps = response.json()
        return stamps

    def get_stamp(self) -> str:
        if self.stamps is None:
            self.stamps = self.get_stamps_from_bluelinky()

        frequency = self.stamps["frequency"]
        generated_at = dateutil.parser.isoparse(self.stamps["generated"])
        position = int(
            (datetime.now(pytz.utc) - generated_at).total_seconds() * 1000.0 / frequency
        )
        stamp_count = len(self.stamps["stamps"])
        _LOGGER.debug(
            f"{DOMAIN} - get_stamp {generated_at} {frequency} {position} {stamp_count} {((datetime.now(pytz.utc) - generated_at).total_seconds()*1000.0)/frequency}"
        )
        if (position * 100.0) / stamp_count > 90:
            self.stamps = None
            return self.get_stamp()
        else:
            return self.stamps["stamps"][position]

    def login(self) -> Token:
        stamp = self.get_stamp()
        self.device_id = self.get_device_id(stamp)
        self.cookies = self.get_cookies()
        self.set_session_language()
        self.authorization_code = None
        try:
            self.authorization_code = self.get_authorization_code_with_redirect_url()
        except Exception as ex1:
            self.authorization_code = self.get_authorization_code_with_form()

        (
            self.access_token,
            self.access_token,
            self.authorization_code,
        ) = self.get_access_token(stamp)

        self.token_type, self.refresh_token = self.get_refresh_token(stamp)

        response = self.get_vehicle()
        vehicle_name = response["vehicles"][0]["nickname"]
        vehicle_id = response["vehicles"][0]["vehicleId"]
        vehicle_model = response["vehicles"][0]["vehicleName"]
        vehicle_registration_date = response["vehicles"][0]["regDate"]
        valid_until = (datetime.now() + timedelta(hours=23)).strftime(DATE_FORMAT)

        token = Token({})
        token.set(
            self.access_token,
            self.refresh_token,
            self.device_id,
            vehicle_name,
            vehicle_id,
            None,
            vehicle_model,
            vehicle_registration_date,
            valid_until,
            stamp,
        )

        return token

    def get_device_id(self, stamp):
        registration_id = 1
        try:
            credentials = push_receiver.register(sender_id=self.GCM_SENDER_ID)
            registration_id = credentials["gcm"]["token"]
        except:
            pass
        url = self.SPA_API_URL + "notifications/register"
        payload = {
            "pushRegId": registration_id,
            "pushType": "GCM",
            "uuid": str(uuid.uuid4()),
        }

        for i in range(0, INVALID_STAMP_RETRY_COUNT):
            headers = {
                "ccsp-service-id": self.CCSP_SERVICE_ID,
                "ccsp-application-id": self.APP_ID,
                "Stamp": stamp,
                "Content-Type": "application/json;charset=UTF-8",
                "Host": self.BASE_URL,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "User-Agent": USER_AGENT_OK_HTTP,
            }

            response = requests.post(url, headers=headers, json=payload)
            response = response.json()
            _LOGGER.debug(f"{DOMAIN} - Get Device ID request {headers} {payload}")
            _LOGGER.debug(f"{DOMAIN} - Get Device ID response {response}")
            if not (response["retCode"] == "F" and response["resCode"] == "4017"):
                break
            _LOGGER.debug(f"{DOMAIN} - Retry count {i} - Invalid stamp {stamp}")

        device_id = response["resMsg"]["deviceId"]
        return device_id

    def get_cookies(self):
        ### Get Cookies ###
        url = (
            self.USER_API_URL
            + "oauth2/authorize?response_type=code&state=test&client_id="
            + self.CLIENT_ID
            + "&redirect_uri="
            + self.USER_API_URL
            + "oauth2/redirect&lang=en"
        )
        payload = {}
        headers = {
            "Host": self.BASE_URL,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": USER_AGENT_MOZILLA,
            "Accept": ACCEPT_HEADER_ALL,
            "X-Requested-With": "com.kia.uvo.eu",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en,en-US;q=0.9",
        }

        _LOGGER.debug(f"{DOMAIN} - Get cookies request {url}")
        session = requests.Session()
        response = session.get(url)
        _LOGGER.debug(f"{DOMAIN} - Get cookies response {session.cookies.get_dict()}")
        return session.cookies.get_dict()
        # return session

    def set_session_language(self):
        ### Set Language for Session ###
        url = self.USER_API_URL + "language"
        headers = {"Content-type": "application/json"}
        payload = {"lang": "en"}
        response = requests.post(
            url, json=payload, headers=headers, cookies=self.cookies
        )

    def get_authorization_code_with_redirect_url(self):
        url = self.USER_API_URL + "signin"
        headers = {"Content-type": "application/json"}
        data = {"email": self.username, "password": self.password}
        response = requests.post(
            url, json=data, headers=headers, cookies=self.cookies
        ).json()
        _LOGGER.debug(f"{DOMAIN} - Sign In Response {response}")
        parsed_url = urlparse(response["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])
        return authorization_code

    def get_authorization_code_with_form(self):
        url = self.USER_API_URL + "integrationinfo"
        headers = {"User-Agent": USER_AGENT_MOZILLA}
        response = requests.get(url, headers=headers, cookies=self.cookies)
        self.cookies = self.cookies | response.cookies.get_dict()
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - IntegrationInfo Response {response}")
        user_id = response["userId"]
        service_id = response["serviceId"]

        login_form_url = self.LOGIN_FORM_URL
        login_form_url = login_form_url.replace("$service_id", service_id)
        login_form_url = login_form_url.replace("$user_id", user_id)

        response = requests.get(login_form_url, headers=headers, cookies=self.cookies)
        self.cookies = self.cookies | response.cookies.get_dict()
        _LOGGER.debug(
            f"{DOMAIN} - LoginForm {login_form_url} - Response {response.text}"
        )
        soup = BeautifulSoup(response.content, "html.parser")
        login_form_action_url = soup.find("form")["action"].replace("&amp;", "&")

        data = {
            "username": self.username,
            "password": self.password,
            "credentialId": "",
            "rememberMe": "on",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT_MOZILLA,
        }
        response = requests.post(
            login_form_action_url,
            data=data,
            headers=headers,
            allow_redirects=False,
            cookies=self.cookies,
        )
        self.cookies = self.cookies | response.cookies.get_dict()
        _LOGGER.debug(
            f"{DOMAIN} - LoginFormSubmit {login_form_action_url} - Response {response.status_code} - {response.headers}"
        )
        if response.status_code != 302:
            _LOGGER.debug(
                f"{DOMAIN} - LoginFormSubmit Error {login_form_action_url} - Response {response.status_code} - {response.text}"
            )
            return

        redirect_url = response.headers["Location"]
        headers = {"User-Agent": USER_AGENT_MOZILLA}
        response = requests.get(redirect_url, headers=headers, cookies=self.cookies)
        self.cookies = self.cookies | response.cookies.get_dict()
        _LOGGER.debug(
            f"{DOMAIN} - Redirect User Id {redirect_url} - Response {response.url} - {response.text}"
        )

        intUserId = 0
        if "account-find-link" in response.text:
            soup = BeautifulSoup(response.content, "html.parser")
            login_form_action_url = soup.find("form")["action"].replace("&amp;", "&")
            data = {"actionType": "FIND", "createToUVO": "UVO", "email": ""}
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT_MOZILLA,
            }
            response = requests.post(
                login_form_action_url,
                data=data,
                headers=headers,
                allow_redirects=False,
                cookies=self.cookies,
            )

            if response.status_code != 302:
                _LOGGER.debug(
                    f"{DOMAIN} - AccountFindLink Error {login_form_action_url} - Response {response.status_code}"
                )
                return

            self.cookies = self.cookies | response.cookies.get_dict()
            redirect_url = response.headers["Location"]
            headers = {"User-Agent": USER_AGENT_MOZILLA}
            response = requests.get(redirect_url, headers=headers, cookies=self.cookies)
            _LOGGER.debug(
                f"{DOMAIN} - Redirect User Id 2 {redirect_url} - Response {response.url}"
            )
            _LOGGER.debug(f"{DOMAIN} - Redirect 2 - Response Text {response.text}")
            parsed_url = urlparse(response.url)
            intUserId = "".join(parse_qs(parsed_url.query)["int_user_id"])
        else:
            parsed_url = urlparse(response.url)
            intUserId = "".join(parse_qs(parsed_url.query)["intUserId"])

        url = self.USER_API_URL + "silentsignin"
        headers = {
            "User-Agent": USER_AGENT_MOZILLA,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
        }
        response = requests.post(
            url, headers=headers, json={"intUserId": intUserId}, cookies=self.cookies
        ).json()
        _LOGGER.debug(f"{DOMAIN} - silentsignin Response {response}")
        parsed_url = urlparse(response["redirectUrl"])
        authorization_code = "".join(parse_qs(parsed_url.query)["code"])
        return authorization_code

    def get_access_token(self, stamp):
        ### Get Access Token ###
        url = self.USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": self.BASIC_AUTHORIZATION,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": self.BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=authorization_code&redirect_uri=https%3A%2F%2F"
            + self.BASE_DOMAIN
            + "%3A8080%2Fapi%2Fv1%2Fuser%2Foauth2%2Fredirect&code="
            + self.authorization_code
        )
        _LOGGER.debug(f"{DOMAIN} - Get Access Token Data {headers }{data}")
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Access Token Response {response}")

        token_type = response["token_type"]
        access_token = token_type + " " + response["access_token"]
        authorization_code = response["refresh_token"]
        _LOGGER.debug(f"{DOMAIN} - Access Token Value {access_token}")
        return token_type, access_token, authorization_code

    def get_refresh_token(self, stamp):
        ### Get Refresh Token ###
        url = self.USER_API_URL + "oauth2/token"
        headers = {
            "Authorization": self.BASIC_AUTHORIZATION,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "Stamp": stamp,
            "Content-type": "application/x-www-form-urlencoded",
            "Host": self.BASE_URL,
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        data = (
            "grant_type=refresh_token&redirect_uri=https%3A%2F%2Fwww.getpostman.com%2Foauth2%2Fcallback&refresh_token="
            + self.authorization_code
        )
        _LOGGER.debug(f"{DOMAIN} - Get Refresh Token Data {data}")
        response = requests.post(url, data=data, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Get Refresh Token Response {response}")
        token_type = response["token_type"]
        refresh_token = token_type + " " + response["access_token"]
        return token_type, refresh_token

    def get_vehicle(self):
        ### Get Vehicles ###
        url = self.SPA_API_URL + "vehicles"
        headers = {
            "Authorization": self.access_token,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "Stamp": self.get_stamp(),
            "ccsp-device-id": self.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Get Vehicles Response {response}")
        response = response["resMsg"]
        return response

    def get_cached_vehicle_status(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/status/latest"
        headers = {
            "Authorization": token.access_token,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "Stamp": self.get_stamp(),
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - get_cached_vehicle_status response {response}")

        try:
            response["resMsg"]["vehicleStatusInfo"][
                "drvhistory"
            ] = self.get_driving_info(token)
        except:
            _LOGGER.warning("Unable to get drivingInfo")

        return response["resMsg"]["vehicleStatusInfo"]

    def get_driving_info(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/drvhistory"
        headers = {
            "Authorization": token.access_token,
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "Stamp": self.get_stamp(),
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        responseAlltime = requests.post(url, json={"periodTarget": 1}, headers=headers)
        responseAlltime = responseAlltime.json()
        _LOGGER.debug(f"{DOMAIN} - get_driving_info responseAlltime {responseAlltime}")

        response30d = requests.post(url, json={"periodTarget": 0}, headers=headers)
        response30d = response30d.json()
        _LOGGER.debug(f"{DOMAIN} - get_driving_info response30d {response30d}")

        drivingInfo = {}

        try:
            drivingInfo = responseAlltime["resMsg"]["drivingInfoDetail"][0]

            for drivingInfoItem in response30d["resMsg"]["drivingInfo"]:
                if drivingInfoItem["drivingPeriod"] == 0:
                    drivingInfo["consumption30d"] = round(
                        drivingInfoItem["totalPwrCsp"]
                        / drivingInfoItem["calculativeOdo"]
                    )
                    break

        except:
            _LOGGER.warning("Unable to parse drivingInfo")

        return drivingInfo

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

    def update_location(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/location"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }
        try:
            response = requests.get(url, headers=headers)
            response = response.json()
            _LOGGER.debug(f"{DOMAIN} - Get Vehicle Location {response}")
            if response["resCode"] != "0000":
                raise Exception("No Location Located")

        except:
            _LOGGER.warning(f"{DOMAIN} - Get vehicle location failed")

    def update_vehicle_status(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/status"
        headers = {
            "Authorization": token.refresh_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        _LOGGER.debug(f"{DOMAIN} - Received forced vehicle data {response}")
        self.update_location(token)

    def lock_action(self, token: Token, action):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/door"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": action, "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Lock Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Lock Action Response {response}")

    def start_climate(
        self, token: Token, set_temp, duration, defrost, climate, heating
    ):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        set_temp = self.get_temperature_range_by_region().index(set_temp)
        set_temp = hex(set_temp).split("x")
        set_temp = set_temp[1] + "H"
        set_temp = set_temp.zfill(3).upper()

        payload = {
            "action": "start",
            "hvacType": 0,
            "options": {
                "defrost": defrost,
                "heating1": int(heating),
            },
            "tempCode": set_temp,
            "unit": "C",
        }
        _LOGGER.debug(f"{DOMAIN} - Start Climate Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Start Climate Action Response {response}")

    def stop_climate(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/temperature"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {
            "action": "stop",
            "hvacType": 0,
            "options": {
                "defrost": True,
                "heating1": 1,
            },
            "tempCode": "10H",
            "unit": "C",
        }
        _LOGGER.debug(f"{DOMAIN} - Stop Climate Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Stop Climate Action Response {response}")

    def start_charge(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": "start", "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Start Charge Action Response {response}")

    def stop_charge(self, token: Token):
        url = self.SPA_API_URL + "vehicles/" + token.vehicle_id + "/control/charge"
        headers = {
            "Authorization": token.access_token,
            "Stamp": self.get_stamp(),
            "ccsp-service-id": self.CCSP_SERVICE_ID,
            "ccsp-application-id": self.APP_ID,
            "ccsp-device-id": token.device_id,
            "Host": self.BASE_URL,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT_OK_HTTP,
        }

        payload = {"action": "stop", "deviceId": token.device_id}
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Request {payload}")
        response = requests.post(url, json=payload, headers=headers).json()
        _LOGGER.debug(f"{DOMAIN} - Stop Charge Action Response {response}")
