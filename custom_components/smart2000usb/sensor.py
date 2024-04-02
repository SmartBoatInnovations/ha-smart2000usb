# Standard Library Imports
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

# Third-Party Library Imports
from asyncio import IncompleteReadError
from aiohttp.client_exceptions import ClientConnectorError

# Home Assistant Imports
from homeassistant.core import callback
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED
)


# Setting up logging and configuring constants and default values

_LOGGER = logging.getLogger(__name__)


async def update_sensor_availability(hass,instance_name):
    """Update the availability of all sensors every 5 minutes."""
    
    created_sensors_key = f"{instance_name}_created_sensors"

    while True:
        _LOGGER.debug("Running update_sensor_availability")
        await asyncio.sleep(300)  # wait for 5 minutes

        for sensor in hass.data[created_sensors_key].values():
            sensor.update_availability()


# The main setup function to initialize the sensor platform

async def async_setup_entry(hass, entry, async_add_entities):
    # Retrieve configuration from entry
    name = entry.data[CONF_NAME]
    host = "0"
    port = "69"

    # Log the retrieved configuration values for debugging purposes
    _LOGGER.info(f"Configuring sensor with name: {name}, host: {host}, port: {port}")
    
    # Initialize unique dictionary keys based on the integration name
    add_entities_key = f"{name}_add_entities"
    created_sensors_key = f"{name}_created_sensors"
    smart2000esp_data_key = f"{name}_smart2000esp_data"

     # Save a reference to the add_entities callback
    _LOGGER.debug(f"Assigning async_add_entities to hass.data[{add_entities_key}].")
    hass.data[add_entities_key] = async_add_entities


    # Initialize a dictionary to store references to the created sensors
    hass.data[created_sensors_key] = {}
    
    # Load the Smart2000 json data 
    config_dir = hass.config.config_dir
    json_path = os.path.join(config_dir, 'custom_components', 'smart2000esp', 'smart2000pgns.json')
    try:
        with open(json_path, "r") as file:
            smart_data = json.load(file)

        pgn_dict = {}
        for pgn in smart_data["PGNs"]:  
            pgn_id = pgn["PGN"] 
            
            pgn_dict[pgn_id] = {
                "Description": pgn["Description"],
                "Type": pgn["Type"],
                "FieldCount": pgn["FieldCount"],
                "Length": pgn.get("Length", 0)
            }

        hass.data[smart2000esp_data_key] = pgn_dict

    except Exception as e:
        _LOGGER.error(f"Error loading Smart2000.json: {e}")
        return

    _LOGGER.debug(f"Loaded smart data: {hass.data[smart2000esp_data_key]}")
    
    
    
    # Define a callback to handle specific sensor state changes
    @callback
    def sensor_state_change(entity_id, old_state, new_state):
        # Log the new value
        if new_state is not None:
            set_pgn_entity(hass, name, entity_id, new_state.state)          
        else:
            _LOGGER.debug('Sensor %s has no new state', entity_id)

    # Subscribe to changes of the specific sensor
    async_track_state_change(hass, 'sensor.esphome_web_3e9a60_s_2000_frame', sensor_state_change)

    _LOGGER.info(f"{name} setup completed.")

def set_pgn_entity(hass, instance_name, entity_id, state_value):
    """Reconstructs PGN and data64 from the sensor state, handling various edge cases."""

    # Check if the state_value is None or does not contain a colon, indicating an invalid or unavailable state
    if state_value is None or ':' not in state_value:
        _LOGGER.debug('Invalid or unavailable state  : %s' , state_value)
        return

    try:
        # Split the state string into PGN, frame counter, and data payload hexadecimal strings
        parts = state_value.split(':')
        if len(parts) < 3:
            _LOGGER.debug('Invalid state format  : %s' , state_value)
            return
    
        pgn_hex, frame_counter_hex, data64_hex = parts[0], parts[1], parts[2]
    
        # Convert the hexadecimal strings back to integer values
        pgn = int(pgn_hex, 16)
        frame_counter = int(frame_counter_hex, 16)
        data64 = int(data64_hex, 16)
    
        # Log the reconstructed values
        _LOGGER.debug('Reconstructed PGN  : %d (Hex: %s)' , pgn, pgn_hex)
        _LOGGER.debug('Reconstructed frame counter  : %d (Hex: %s)' , frame_counter, frame_counter_hex)
        _LOGGER.debug('Reconstructed data64  : %d (Hex: %s)' , data64, data64_hex)
        
            
        if pgn == 128259:
            process_pgn_128259(hass, instance_name, entity_id, data64)
        elif pgn == 128267:
            process_pgn_128267(hass, instance_name, entity_id, data64)
        elif pgn == 128275:
            process_pgn_128275(hass, instance_name, entity_id, data64)
        elif pgn == 130311:
            process_pgn_130311(hass, instance_name, entity_id, data64)
        else:
            _LOGGER.debug('Unsupported PGN %d for entity %s.', pgn, entity_id)

    except ValueError as e:
        _LOGGER.error('Error processing state value  : %s. Error: %s' , state_value, e)


def publish_field(hass, instance_name, field_name, field_description, field_value, pgn_description, unit, pgn_id):
    _LOGGER.debug(f"Publishing field for PGN {pgn_id} and field {field_name} with value {field_value}")

    add_entities_key = f"{instance_name}_add_entities"
    created_sensors_key = f"{instance_name}_created_sensors"
    smart2000esp_data_key = f"{instance_name}_smart2000esp_data"

    # Construct unique sensor name
    sensor_name = f"{instance_name}_{pgn_id}_{field_name}"
    _LOGGER.debug(f"Constructed sensor name: {sensor_name}")

    # Define sensor characteristics
    group = "N2000"
    unit_of_measurement = unit  # Determine based on field_name if applicable
    
    device_name = pgn_description
    _LOGGER.debug(f"Device name for PGN {pgn_id}: {device_name}")

    # Access keys for created sensors and entity addition
    created_sensors_key = f"{instance_name}_created_sensors"
    add_entities_key = f"{instance_name}_add_entities"

    # Check for sensor existence and create/update accordingly
    if sensor_name not in hass.data[created_sensors_key]:
        _LOGGER.debug(f"Creating new sensor for {sensor_name}")
        # If sensor does not exist, create and add it
        sensor = SmartSensor(
            sensor_name, 
            field_description, 
            field_value, 
            group, 
            unit_of_measurement, 
            device_name, 
            pgn_id
        )
        
        hass.data[add_entities_key]([sensor])
        hass.data[created_sensors_key][sensor_name] = sensor
        _LOGGER.debug(f"Sensor {sensor_name} added successfully.")
    else:
        # If sensor exists, update its state
        _LOGGER.debug(f"Updating existing sensor {sensor_name} with new value: {field_value}")
        sensor = hass.data[created_sensors_key][sensor_name]
        sensor.set_state(field_value)
        _LOGGER.debug(f"Sensor {sensor_name} updated successfully.")

        
def process_pgn_128259(hass, instance_name, entity_id, data64):
    """Process and log data for PGN 128259."""
    if data64 is not None:
        # sid | Offset: 0, Length: 8, Resolution: 1
        sid_raw = (data64 & 0x00000000000000FF) >> 0
        sid = sid_raw * 1
        publish_field(hass, instance_name, 'sid', 'SID', sid, 'Speed', '', '128259')
        _LOGGER.debug('SID  : %s', sid)

        # speed_water_referenced | Offset: 8, Length: 16, Resolution: 0.01
        speed_water_referenced_raw = (data64 & 0x0000000000FFFF00) >> 8
        speed_water_referenced = speed_water_referenced_raw * 0.01
        publish_field(hass, instance_name, 'speed_water_referenced', 'Speed Water Referenced', speed_water_referenced, 'Speed', 'm/s', '128259')
        _LOGGER.debug('Speed Water Referenced  : %s', speed_water_referenced)

        # speed_ground_referenced | Offset: 24, Length: 16, Resolution: 0.01
        speed_ground_referenced_raw = (data64 & 0x000000FFFF000000) >> 24
        speed_ground_referenced = speed_ground_referenced_raw * 0.01
        publish_field(hass, instance_name, 'speed_ground_referenced', 'Speed Ground Referenced', speed_ground_referenced, 'Speed', 'm/s', '128259')
        _LOGGER.debug('Speed Ground Referenced  : %s', speed_ground_referenced)

        # speed_water_referenced_type | Offset: 40, Length: 8, Resolution: 1
        speed_water_referenced_type_raw = (data64 & 0x0000FF0000000000) >> 40
        speed_water_referenced_type = speed_water_referenced_type_raw * 1
        publish_field(hass, instance_name, 'speed_water_referenced_type', 'Speed Water Referenced Type', speed_water_referenced_type, 'Speed', '', '128259')
        _LOGGER.debug('Speed Water Referenced Type  : %s', speed_water_referenced_type)

        # speed_direction | Offset: 48, Length: 4, Resolution: 1
        speed_direction_raw = (data64 & 0x000F000000000000) >> 48
        speed_direction = speed_direction_raw * 1
        publish_field(hass, instance_name, 'speed_direction', 'Speed Direction', speed_direction, 'Speed', '', '128259')
        _LOGGER.debug('Speed Direction  : %s', speed_direction)

        # reserved | Offset: 52, Length: 12, Resolution: 1
        reserved_raw = (data64 & 0xFFF0000000000000) >> 52
        reserved = reserved_raw * 1
        publish_field(hass, instance_name, 'reserved', 'Reserved', reserved, 'Speed', '', '128259')
        _LOGGER.debug('Reserved  : %s', reserved)

    else:
        _LOGGER.debug('No data64 provided for PGN 128259 processing.', entity_id)

def process_pgn_128267(hass, instance_name, entity_id, data64):
    """Process and log data for PGN 128267."""
    if data64 is not None:
        # sid | Offset: 0, Length: 8, Resolution: 1
        sid_raw = (data64 & 0x00000000000000FF) >> 0
        sid = sid_raw * 1
        publish_field(hass, instance_name, 'sid', 'SID', sid, 'Water Depth', '', '128267')
        _LOGGER.debug('SID  : %s', sid)

        # depth | Offset: 8, Length: 32, Resolution: 0.01
        depth_raw = (data64 & 0x000000FFFFFFFF00) >> 8
        depth = depth_raw * 0.01
        publish_field(hass, instance_name, 'depth', 'Depth', depth, 'Water Depth', 'm', '128267')
        _LOGGER.debug('Depth  : %s', depth)

        # offset | Offset: 40, Length: 16, Resolution: 0.001
        offset_raw = (data64 & 0x00FFFF0000000000) >> 40
        if offset_raw & (1 << (16 - 1)):
            offset_raw -= (1 << 16)
        offset = offset_raw * 0.001
        publish_field(hass, instance_name, 'offset', 'Offset', offset, 'Water Depth', 'm', '128267')
        _LOGGER.debug('Offset  : %s', offset)

        # range | Offset: 56, Length: 8, Resolution: 10
        range_raw = (data64 & 0xFF00000000000000) >> 56
        range = range_raw * 10
        publish_field(hass, instance_name, 'range', 'Range', range, 'Water Depth', 'm', '128267')
        _LOGGER.debug('Range  : %s', range)

    else:
        _LOGGER.debug('No data64 provided for PGN 128267 processing.', entity_id)

def process_pgn_128275(hass, instance_name, entity_id, data64):
    """Process and log data for PGN 128275."""
    if data64 is not None:
        # date | Offset: 0, Length: 16, Resolution: 1
        date_raw = (data64 & 0x000000000000FFFF) >> 0
        date = date_raw * 1
        publish_field(hass, instance_name, 'date', 'Date', date, 'Distance Log', 'd', '128275')
        _LOGGER.debug('Date  : %s', date)

        # time | Offset: 16, Length: 32, Resolution: 0.0001
        time_raw = (data64 & 0x0000FFFFFFFF0000) >> 16
        time = time_raw * 0.0001
        publish_field(hass, instance_name, 'time', 'Time', time, 'Distance Log', 's', '128275')
        _LOGGER.debug('Time  : %s', time)

        # log | Offset: 48, Length: 32, Resolution: 1
        log_raw = (data64 & 0xFFFFFFFF000000000000) >> 48
        log = log_raw * 1
        publish_field(hass, instance_name, 'log', 'Log', log, 'Distance Log', 'm', '128275')
        _LOGGER.debug('Log  : %s', log)

        # trip_log | Offset: 80, Length: 32, Resolution: 1
        trip_log_raw = (data64 & 0xFFFFFFFF00000000000000000000) >> 80
        trip_log = trip_log_raw * 1
        publish_field(hass, instance_name, 'trip_log', 'Trip Log', trip_log, 'Distance Log', 'm', '128275')
        _LOGGER.debug('Trip Log  : %s', trip_log)

    else:
        _LOGGER.debug('No data64 provided for PGN 128275 processing.', entity_id)

def process_pgn_130311(hass, instance_name, entity_id, data64):
    """Process and log data for PGN 130311."""
    if data64 is not None:
        # sid | Offset: 0, Length: 8, Resolution: 1
        sid_raw = (data64 & 0x00000000000000FF) >> 0
        sid = sid_raw * 1
        publish_field(hass, instance_name, 'sid', 'SID', sid, 'Environmental Parameters', '', '130311')
        _LOGGER.debug('SID  : %s', sid)

        # temperature_source | Offset: 8, Length: 6, Resolution: 1
        temperature_source_raw = (data64 & 0x0000000000003F00) >> 8
        temperature_source = temperature_source_raw * 1
        publish_field(hass, instance_name, 'temperature_source', 'Temperature Source', temperature_source, 'Environmental Parameters', '', '130311')
        _LOGGER.debug('Temperature Source  : %s', temperature_source)

        # humidity_source | Offset: 14, Length: 2, Resolution: 1
        humidity_source_raw = (data64 & 0x000000000000C000) >> 14
        humidity_source = humidity_source_raw * 1
        publish_field(hass, instance_name, 'humidity_source', 'Humidity Source', humidity_source, 'Environmental Parameters', '', '130311')
        _LOGGER.debug('Humidity Source  : %s', humidity_source)

        # temperature | Offset: 16, Length: 16, Resolution: 0.01
        temperature_raw = (data64 & 0x00000000FFFF0000) >> 16
        temperature = temperature_raw * 0.01
        publish_field(hass, instance_name, 'temperature', 'Temperature', temperature, 'Environmental Parameters', 'K', '130311')
        _LOGGER.debug('Temperature  : %s', temperature)

        # humidity | Offset: 32, Length: 16, Resolution: 0.004
        humidity_raw = (data64 & 0x0000FFFF00000000) >> 32
        if humidity_raw & (1 << (16 - 1)):
            humidity_raw -= (1 << 16)
        humidity = humidity_raw * 0.004
        publish_field(hass, instance_name, 'humidity', 'Humidity', humidity, 'Environmental Parameters', '%', '130311')
        _LOGGER.debug('Humidity  : %s', humidity)

        # atmospheric_pressure | Offset: 48, Length: 16, Resolution: 100
        atmospheric_pressure_raw = (data64 & 0xFFFF000000000000) >> 48
        atmospheric_pressure = atmospheric_pressure_raw * 100
        publish_field(hass, instance_name, 'atmospheric_pressure', 'Atmospheric Pressure', atmospheric_pressure, 'Environmental Parameters', 'Pa', '130311')
        _LOGGER.debug('Atmospheric Pressure  : %s', atmospheric_pressure)

    else:
        _LOGGER.debug('No data64 provided for PGN 130311 processing.', entity_id)



async def set_smart_sensors(hass, line, instance_name):
    """Process the content of the line related to the smart sensors."""
    try:
        if not line or not line.startswith("$"):
            return

        # Splitting by comma and getting the data fields
        fields = line.split(',')
        if len(fields) < 1 or len(fields[0]) < 6:  # Ensure enough fields and length
            _LOGGER.error(f"Malformed line: {line}")
            return

        sentence_id = fields[0][1:6]  # Gets the 5-char word after the $
        device_id = sentence_id[0:2] # Gets the 2-char sender id (pos 2 & 3 of sentence)

        _LOGGER.debug(f"Sentence_id: {sentence_id}, device_id: {device_id}")
        
        # Dynamically construct the keys based on the instance name
        smart0183tcp_data_key = f"{instance_name}_smart0183tcp_data"
        created_sensors_key = f"{instance_name}_created_sensors"
        add_entities_key = f"{instance_name}_add_entities"

        for idx, field_data in enumerate(fields[1:], 1):
            if idx == len(fields) - 1:  # Skip the last field since it's a check digit
                break

            sentence_type = sentence_id[2:]
            sensor_name = f"{device_id}_{sentence_type}_{idx}"

            if sensor_name not in hass.data[created_sensors_key]:
                _LOGGER.debug(f"Creating field sensor: {sensor_name}")
                
                short_sensor_name = f"{sentence_id[2:]}_{idx}"
                sensor_info = hass.data[smart0183tcp_data_key].get(short_sensor_name)
                
                # If sensor_info does not exist, skip this loop iteration
                if sensor_info is None:
                    _LOGGER.debug(f"Skipping creation/update for undefined sensor: {sensor_name}")
                    continue


                full_desc = sensor_info["full_description"] if sensor_info else sensor_name
                group = sensor_info["group"]
                sentence_description = sensor_info["sentence_description"]
                unit_of_measurement = sensor_info.get("unit_of_measurement")

                device_name = sentence_description + ' (' + device_id + ')'

                sensor = SmartSensor(
                    sensor_name, 
                    full_desc, 
                    field_data, 
                    group, 
                    unit_of_measurement, 
                    device_name, 
                    sentence_type
                )
                
                # Add Sensor to Home Assistant
                hass.data[add_entities_key]([sensor])
                
                # Update dictionary with added sensor
                hass.data[created_sensors_key][sensor_name] = sensor
            else:
                _LOGGER.debug(f"Updating field sensor: {sensor_name}")
                sensor = hass.data[created_sensors_key][sensor_name]
                sensor.set_state(field_data)

    except IndexError:
        _LOGGER.error(f"Index error for line: {line}")
    except KeyError as e:
        _LOGGER.error(f"Key error: {e}")
    except Exception as e:
        _LOGGER.error(f"An unexpected error occurred: {e}")


# SmartSensor class representing a basic sensor entity with state

class SmartSensor(Entity):
    def __init__(
        self, 
        name, 
        friendly_name, 
        initial_state, 
        group=None, 
        unit_of_measurement=None, 
        device_name=None, 
        sentence_type=None
    ):
        """Initialize the sensor."""
        _LOGGER.info(f"Initializing sensor: {name} with state: {initial_state}")

        self._unique_id = name.lower().replace(" ", "_")
        self.entity_id = f"sensor.{self._unique_id}"
        self._name = friendly_name if friendly_name else self._unique_id
        self._state = initial_state
        self._group = group if group is not None else "Other"
        self._device_name = device_name
        self._sentence_type = sentence_type
        self._unit_of_measurement = unit_of_measurement
        self._state_class = SensorStateClass.MEASUREMENT
        self._last_updated = datetime.now()
        if initial_state is None or initial_state == "":
            self._available = False
            _LOGGER.debug(f"Setting sensor: '{self._name}' with unavailable")
        else:
            self._available = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_info(self):
        """Return device information about this sensor."""
        return {
            "identifiers": {("smart0183tcp", self._device_name)},
            "name": self._device_name,
            "manufacturer": self._group,
            "model": self._sentence_type,
        }

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return self._state_class


    @property
    def last_updated(self):
        """Return the last updated timestamp of the sensor."""
        return self._last_updated

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self._available

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement for this sensor."""
        return False


    def update_availability(self):
        """Update the availability status of the sensor."""

        new_availability = (datetime.now() - self._last_updated) < timedelta(minutes=4)

        self._available = new_availability

        try:
            self.async_schedule_update_ha_state()
        except RuntimeError as re:
            if "Attribute hass is None" in str(re):
                pass  # Ignore this specific error
            else:
                _LOGGER.warning(f"Could not update state for sensor '{self._name}': {re}")
        except Exception as e:  # Catch all other exception types
            _LOGGER.warning(f"Could not update state for sensor '{self._name}': {e}")

    def set_state(self, new_state):
        """Set the state of the sensor."""
        _LOGGER.debug(f"Setting state for sensor: '{self._name}' to {new_state}")
        self._state = new_state
        if new_state is None or new_state == "":
            self._available = False
            _LOGGER.debug(f"Setting sensor:'{self._name}' with unavailable")
        else:
            self._available = True
        self._last_updated = datetime.now()

        try:
            self.async_schedule_update_ha_state()
        except RuntimeError as re:
            if "Attribute hass is None" in str(re):
                pass  # Ignore this specific error
            else:
                _LOGGER.warning(f"Could not update state for sensor '{self._name}': {re}")
        except Exception as e:  # Catch all other exception types
            _LOGGER.warning(f"Could not update state for sensor '{self._name}': {e}")



