"""
Copyright (c) 2024 Smart Boat Innovations

Version 1.0, 01 June 2024

This file is part of the Smart Boat Innovations software.

Smart Boat Innovations ("Licensor") grants you a limited, non-exclusive, non-transferable, revocable license to load and use this software through Home Assistant Community Store (HACS) for personal, non-commercial use only.

You may not copy, distribute, or modify this file or the accompanying software. The software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.

See the full license text in the accompanying LICENSE file.
"""
# Standard Library Imports

from datetime import date, timedelta
import struct
import math
import logging

_LOGGER = logging.getLogger(__name__)

def kelvin_to_fahrenheit(kelvin):
    """
    Converts temperature from Kelvin to Fahrenheit.
    Returns:
        float: The temperature in Fahrenheit.
    """
    if kelvin is None:
        return None
    
    # Convert Kelvin to Fahrenheit
    fahrenheit = round((kelvin - 273.15) * (9/5) + 32,0)

    return fahrenheit


def kelvin_to_celsius(kelvin):
    """
    Converts temperature from Kelvin to Celsius.
    Returns:
        float: The temperature in Celsius.
    """
    if kelvin is None:
        return None

    # Convert Kelvin to Celsius
    celsius = round(kelvin - 273.15,1)

    return celsius

def mps_to_knots(mps):
    """
    Converts speed from meters per second (m/s) to nautical knots.
    Returns:
        float: The speed in nautical knots, rounded to one decimal place.
    """
    if mps is None:
        return None
    
    # Conversion factor from m/s to knots
    conversion_factor = 3600 / 1852
    
    # Convert m/s to knots and round to one decimal place
    knots = round(mps * conversion_factor, 1)

    return knots


def radians_to_degrees(radians):
    """
    Converts an angle from radians to degrees.
    Returns:
        float: The angle in degrees.
    """
    if radians is None:
        return None

    # Convert radians to degrees
    degrees = round(math.degrees(radians), 0)
    return degrees



def decode_date(days_since_epoch):
    """
    Decodes an integer representing the number of days since 1970-01-01 (UNIX epoch)
    Returns:
        str: The decoded date in YYYY-MM-DD format.
    """
    # Ensure the input is treated as an integer
    days_since_epoch = int(days_since_epoch)
    
    # Define the start date as 1970-01-01
    start_date = date(1970, 1, 1)
    
    # Calculate the decoded date by adding the days to the start date
    decoded_date = start_date + timedelta(days=days_since_epoch)

    # Format and return the date string
    return decoded_date.isoformat()


def decode_time(seconds_since_midnight):
    """
    Decodes an integer representing seconds since midnight into a human-readable time string.
    Returns:
        str: The decoded time in HH:MM:SS format.
    """
    # Ensure the input is treated as an integer
    seconds_since_midnight = int(seconds_since_midnight)

    # Validate input
    if not (0 <= seconds_since_midnight < 86400):  # There are 86400 seconds in a day
        return "0:0:0"

    hours = seconds_since_midnight // 3600  # 3600 seconds in an hour
    minutes = (seconds_since_midnight % 3600) // 60
    seconds = seconds_since_midnight % 60

    # Format and return the time string
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

def decode_duration(seconds, decimals=1):
    """
    Convert an arbitrary duration in seconds to hours (float), rounded.
    Suitable for values that can exceed 24h (e.g., lifetime engine hours).
    """
    if seconds is None:
        return None
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        return None
    hours = sec / 3600.0
    return round(hours, decimals)


def decode_decimal(number_int):
    """
    Decodes a numeric value where each byte represents 2 decimal digits in BCD format.
    """
    # Initialize an empty string to hold the decoded digits
    decoded_digits = ''
    
    # Continue until all digits are processed
    while number_int > 0:
        # Extract the two least significant digits from the current byte
        # (number_int & 0xFF) isolates the least significant byte.
        # Then it's converted to a 2-digit decimal string with format().
        current_byte = number_int & 0xFF
        decoded_digits = '{:02d}'.format(current_byte) + decoded_digits
        
        # Shift right by one byte (8 bits) to process the next byte
        number_int >>= 8

    # Convert the string of digits to an integer
    return int(decoded_digits)


def decode_float(number_int):
    """
    Decodes a 32-bit integer representing an IEEE-754 floating-point number in little endian format into a Python float.
    """
    # Ensure the input integer fits in 32 bits
    if not (0 <= number_int <= 0xFFFFFFFF):
        return 0

    # Convert the integer to bytes. The '<I' format specifies little-endian unsigned 32-bit integer.
    bytes_data = struct.pack('<I', number_int)

    # Unpack the bytes to a float using the '<f' format which specifies little-endian 32-bit floating point.
    decoded_float, = struct.unpack('<f', bytes_data)

    return decoded_float


def decode_number(number_int, bit_length):
    """
    The function follows specific decoding rules based on the bit length of the number:
    - For numbers using 2 or 3 bits, the maximum value indicates the field is not present (0 is returned).
    - For numbers using 4 bits or more, two special conditions are checked:
        - The maximum positive value indicates the field is not present (0 is returned).
    """

    # Log the input and calculated bit length for debugging
    _LOGGER.debug(f"Decoding number: {number_int}, Bit length: {bit_length}")

    if bit_length <= 3:
        if number_int == (1 << bit_length) - 1:
            _LOGGER.debug(f"Field not present for bit length <= 3. Number: {number_int}")
            return None
    elif bit_length >= 4:
        max_positive_value = (1 << bit_length) - 1
        if number_int == max_positive_value:
            _LOGGER.debug(f"Field not present for bit length >= 4. Number: {number_int}")
            return None
        elif number_int == max_positive_value - 1:
            _LOGGER.debug(f"Field has an error for bit length >= 4. Number: {number_int}")
            return None

    # If no special conditions met, log and return the number as is
    _LOGGER.debug(f"No special conditions met. Returning number: {number_int}")
    return number_int
