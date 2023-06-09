import json
import logging
import os

# Define the paths to the config files
SYSTEM_CONFIG_PATH = "theta_tracker_system.conf"
USER_CONFIG_PATH = "theta_tracker_user.conf"

def create_system_config():
    """Create the system config file with the API key and refresh interval."""
    # Ask the user for the API key
    api_key = input("Please enter your API key: ")

    # Create the system config file
    try:
        with open(SYSTEM_CONFIG_PATH, "w") as f:
            json.dump({"api_key": api_key, "refresh_interval": 300}, f)
    except IOError:
        raise IOError("Error: Unable to create system config file.")

def load_system_config():
    """Load the system configuration, creating it if necessary."""
    if not os.path.exists(SYSTEM_CONFIG_PATH):
        create_system_config()
    try:
        with open(SYSTEM_CONFIG_PATH, "r") as f:
            return json.load(f)
    except IOError:
        raise IOError("Error: Unable to read system config file.")

def load_user_config():
    """Load the user configuration, creating it if necessary."""
    if not os.path.exists(USER_CONFIG_PATH):
        create_user_config()
    try:
        with open(USER_CONFIG_PATH, "r") as f:
            return json.load(f)
    except IOError:
        raise IOError("Error: Unable to read user config file.")
    except json.decoder.JSONDecodeError as e:
        raise ValueError(f"Error: Unable to parse JSON data in user config file. JSONDecodeError: {e}")

def create_user_config():
    # Ask the user for the config values
    while True:
        try:
            max_delta = float(input("Please enter the maximum delta (0.0 - 1.0): "))
            if not 0.0 <= max_delta <= 1.0:
                print("Error: Delta range must be between 0.0 and 1.0.")
                continue

            dte_range_min = int(input("Please enter the DTE range minimum (0 - 365): "))
            if not 0 <= dte_range_min <= 365:
                print("Error: DTE range minimum must be between 0 and 365.")
            dte_range_max = int(input("Please enter the DTE range maximum ({} - 365): ".format(dte_range_min)))
            if not dte_range_min <= dte_range_max <= 365:
                print("Error: DTE range maximum must be between {} and 365: ".format(dte_range_min))
                continue

            buying_power = float(input("Please enter the buying power (greater than $1000): "))
            if buying_power <= 1000:
                print("Error: Buying power must be greater than $1000.")
                continue

            break
        except ValueError:
            print("Error: Invalid input. Please try again.")

    # Create the user config file
    try:
        with open(USER_CONFIG_PATH, "w") as f:
            json.dump({
                "max_delta": max_delta,
                "dte_range_min": dte_range_min,
                "dte_range_max": dte_range_max,
                "buying_power": buying_power,
                "default_sorting_method": "premium_usd",
                "tickers": ["SPY"],
            }, f)
    except IOError:
        print("Error: Unable to create user config file.")
        exit(1)

def validate_max_delta(value):
    try:
        value = float(value)
        logging.debug("konwersja do float udała się")
        if 0.0 <= value <= 1.0:
            logging.debug("wartość jest OK")
            return True, None
        else:
            return False, "Delta range must be between 0.0 and 1.0."
    except ValueError:
        return False, "Invalid input. Please enter a valid number."
def validate_dte_range_min(value):
    try:
        value = int(value)
        if 0 <= value <= 365:
            return True, None
        else:
            return False, "Error: DTE range minimum must be between 0 and 365."
    except ValueError:
        return False, "Invalid input. Please enter a valid number."

def validate_dte_range_max(dte_range_min, value):
    try:
        value = int(value)
        if int(dte_range_min) <= value <= 365:
            return True, None
        else:
            return False, "Error: DTE range maximum must be between {} and 365: ".format(dte_range_min)
    except ValueError:
        return False, "Invalid input. Please enter a valid number."

def validate_buying_power(value):
    try:
        value = float(value)
        if value >= 1000:
            return True, None
        else:
            return False, "Buying power must be greater than or equal to $1000."
    except ValueError:
        return False, "Invalid input. Please enter a valid number."


def save_user_config(user_config):
    # Save the user config file
    try:
        with open(USER_CONFIG_PATH, "w") as f:
            json.dump(user_config, f)
    except IOError:
        print("Error: Unable to save user config file.")
        exit(1)