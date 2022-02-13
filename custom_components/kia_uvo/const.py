"""Constants for the Hyundai / Kia Connect integration."""

DOMAIN: str = "kia_uvo"

CONF_BRAND: str = "brand"
CONF_FORCE_REFRESH_INTERVAL: str = "force_refresh"
CONF_NO_FORCE_REFRESH_HOUR_START: str = "no_force_refresh_hour_start"
CONF_NO_FORCE_REFRESH_HOUR_FINISH: str = "no_force_refresh_hour_finish"

REGION_EUROPE: str = "Europe"
REGION_CANADA: str = "Canada"
REGION_USA: str = "USA"
REGIONS = {1: REGION_EUROPE, 2: REGION_CANADA, 3: REGION_USA}
BRAND_KIA: str = "Kia"
BRAND_HYUNDAI: str = "Hyundai"
BRANDS = {1: BRAND_KIA, 2: BRAND_HYUNDAI}

DEFAULT_PIN: str = ""
DEFAULT_SCAN_INTERVAL: int = 30
DEFAULT_FORCE_REFRESH_INTERVAL: int = 240
DEFAULT_NO_FORCE_REFRESH_HOUR_START: int = 22
DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH: int = 6

DYNAMIC_UNIT: str = "dynamic_unit"

SEAT_STATUS = {
    None: None,
    0: "Off",
    1: "On",
    2: "Off",
    3: "Low Cool",
    4: "Medium Cool",
    5: "High Cool",
    6: "Low Heat",
    7: "Medium Heat",
    8: "High Heat",
}

HEAT_STATUS = {
    None: None,
    0: "Off",
    1: "Steering Wheel and Rear Window",
    2: "Rear Window Only",
    3: "Steering Wheel Only",
}