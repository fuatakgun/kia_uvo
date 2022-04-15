import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_USERNAME,
    CONF_REGION,
    CONF_PIN,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
import hashlib

from .const import DOMAIN, CONF_BRAND, DEFAULT_PIN, BRANDS, REGIONS
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
]


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry):
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hyundai / Kia Connect from a config entry."""
    coordinator = HyundaiKiaConnectDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.unique_id] = coordinator
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN][config_entry.unique_id]
    if not hass.data[DOMAIN]:
        async_unload_services(hass)
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):

    if config_entry.version == 1:
        _LOGGER.debug(f"{DOMAIN} - config data- {config_entry}")
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        pin = config_entry.data.get(CONF_PIN, DEFAULT_PIN)
        region = config_entry.data.get(CONF_REGION, "")
        brand = config_entry.data.get(CONF_BRAND, "")
        title = f"{BRANDS[brand]} {REGIONS[region]} {username}"
        unique_id = hashlib.sha256(title.encode("utf-8")).hexdigest()
        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_PIN: pin,
            CONF_REGION: region,
            CONF_BRAND: brand,
        }
        registry = hass.helpers.entity_registry.async_get(hass)
        entities = hass.helpers.entity_registry.async_entries_for_config_entry(
            registry, config_entry.entry_id
        )
        for entity in entities:
            registry.async_remove(entity.entity_id)

        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, title=title, data=new_data
        )
        config_entry.version = 2
        _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
