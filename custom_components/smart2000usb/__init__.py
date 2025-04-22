"""Smart Boat 2000 USB Integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging

DOMAIN = "smart2000usb"

_LOGGER = logging.getLogger(__name__)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Options for Smart2000USB have been updated - applying changes")
    # Reload the integration to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict):
    _LOGGER.debug("Setting up Smart2000USB integration")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Setting up Smart2000USB integration entry: %s", entry.as_dict())
    hass.data.setdefault(DOMAIN, {})

    # Register the update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Forward the setup to the sensor platform
    platforms = ["sensor"]
    _LOGGER.debug("Forwarding setup to platforms: %s", platforms)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    _LOGGER.debug("Smart2000USB entry setup completed successfully and update listener registered")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Unloading Smart2000USB integration entry: %s", entry.as_dict())
    hass.data[DOMAIN].pop(entry.entry_id)
    
    # Forward the unload to the sensor platform(s)
    platforms = ["sensor"]
    _LOGGER.debug("Forwarding unload to platforms: %s", platforms)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    _LOGGER.debug("Unload forwarded with result: %s", unload_ok)
    
    _LOGGER.debug("Smart2000USB entry unloaded successfully")
    return True

