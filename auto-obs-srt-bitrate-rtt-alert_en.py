"""
auto-obs-srt-bitrate-rtt-alert_en v1.0.0

This program monitors the bitrate and RTT (Round Trip Time) of an SRT server,
and automatically shows/hides specific sources in OBS scenes when values fall below/rise above thresholds.

Required packages:
- obs-websocket-py
- requests

Configuration file (abc_config.json) must be in the same directory as the program.
"""

import time
import requests
import json
from obswebsocket import obsws, requests as obsrequests
import threading
import logging

# Version information
VERSION = "1.0.0"

# Display version at startup
print(f"\nauto-obs-srt-bitrate-rtt-alert_en v{VERSION}")
print("=" * 50 + "\n")

# Disable unnecessary log messages from OBS WebSocket library
logging.getLogger('websockets.client').setLevel(logging.ERROR)
logging.getLogger('obswebsocket').setLevel(logging.ERROR)

# Program logger setup
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class BitrateMonitor:
    def __init__(self, config_path):
        """Initialize function
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config = self._load_config(config_path)
        self._validate_config(self.config)
        self.ws = None                    # OBS WebSocket connection object
        self.last_sent_time = 0           # Last warning time
        self.ignore_count = 0             # Initial check ignore counter
        self.warning_active = False       # Warning activation status
        self.bitrate_none_logged = False  # Bitrate none logged status
        self.server_connected = False     # Server connection status
        self.server_retry_count = 0       # Server reconnection attempt count
        self.obs_retry_count = 0          # OBS reconnection attempt count
        self.source_id = None             # OBS source ID cache
        self.is_connected = False         # OBS connection status
        self.connect_to_obs()             # Initial OBS connection

    def _validate_config(self, config):
        """Validate configuration values
        
        Args:
            config (dict): Configuration dictionary
            
        Raises:
            ValueError: If configuration values are invalid
        """
        validation_rules = {
            "BITRATE_THRESHOLD": lambda x: isinstance(x, (int, float)) and x > 0,
            "SOURCE_DISPLAY_TIME": lambda x: isinstance(x, (int, float)) and x > 1,
            "COOLDOWN_SECONDS": lambda x: isinstance(x, (int, float)) and x > config["SOURCE_DISPLAY_TIME"],
            "OBS_PORT": lambda x: isinstance(x, int) and x > 0,
            "RTT_THRESHOLD": lambda x: isinstance(x, (int, float)) and x > 1
        }
        
        string_fields = ["STATS_URL", "PUBLISHER", "OBS_HOST", "OBS_PASSWORD", "SOURCE_NAME", "SCENE_NAME"]
        
        # Validate numeric fields
        for field, validator in validation_rules.items():
            if not validator(config[field]):
                raise ValueError(f"Invalid configuration value for {field}")
        
        # Validate string fields
        if not all(isinstance(config.get(field), str) and config.get(field) for field in string_fields):
            raise ValueError("Required string configuration values are missing or invalid")

    def get_retry_delay(self, retry_count):
        """Calculate reconnection wait time (exponential backoff)
        
        Args:
            retry_count (int): Number of retry attempts
            
        Returns:
            int: Wait time in seconds
        """
        # Exponentially increase from 2 seconds up to 32 seconds
        delay = min(2 * (2 ** retry_count), 32)
        return delay

    def connect_to_obs(self):
        """
        Establish OBS WebSocket connection
        
        Returns:
            bool: Connection success status
        """
        try:
            if self.ws:  # Disconnect existing connection if any
                self.ws.disconnect()
            
            # Create new WebSocket connection
            self.ws = obsws(self.config["OBS_HOST"], self.config["OBS_PORT"], self.config["OBS_PASSWORD"])
            self.ws.connect()
            self.is_connected = True
            logger.info("OBS WebSocket connection successful")
            self.obs_retry_count = 0  # Reset retry counter on successful connection
            self.source_id = None  # Reset source ID cache
            return True
        except Exception as e:
            if self.is_connected:
                logger.error("OBS WebSocket connection lost")
                self.is_connected = False
            delay = self.get_retry_delay(self.obs_retry_count)
            logger.error(f"OBS WebSocket connection failed: {e}. Retrying in {delay} seconds...")
            self.obs_retry_count += 1
            return False

    def ensure_obs_connection(self):
        # Check OBS WebSocket connection status and reconnect if needed
        if not self.ws or not self.ws.ws.connected:
            if self.is_connected:  # If previously connected
                logger.error("OBS WebSocket connection lost")
                self.is_connected = False
            return self.connect_to_obs()
        return True

    def _load_config(self, config_path):
        # Load configuration file and check required fields
        try:
            with open(config_path, "r") as config_file:
                config = json.load(config_file)
                required_fields = ["STATS_URL", "PUBLISHER", "OBS_HOST", 
                                 "OBS_PORT", "OBS_PASSWORD", "SOURCE_NAME",
                                 "SCENE_NAME", "BITRATE_THRESHOLD", "RTT_THRESHOLD",
                                 "COOLDOWN_SECONDS", "SOURCE_DISPLAY_TIME"]
                if not all(field in config for field in required_fields):
                    raise ValueError("Required configuration fields are missing")
                return config
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration file: {e}")

    def _fetch_bitrate(self):
        """Fetch bitrate and RTT information from SRT server
        
        Returns:
            tuple: (bitrate, RTT, server_connection_status)
        """
        try:
            if not hasattr(self, 'session'):
                self.session = requests.Session()
            
            response = self.session.get(self.config["STATS_URL"], timeout=1)
            response.raise_for_status()
            
            if not self.server_connected:
                logger.info("SRT server connection successful")
                self.server_connected = True
                self.server_retry_count = 0
            
            data = response.json()
            publishers = data.get("publishers", {})
            publisher_data = publishers.get(self.config["PUBLISHER"], {})
            bitrate = publisher_data.get("bitrate")
            rtt = publisher_data.get("rtt", 0)
            
            if bitrate is None and not self.bitrate_none_logged:
                logger.info("No stream detected. Waiting for stream to start...")
                self.bitrate_none_logged = True
            elif bitrate is not None:
                self.bitrate_none_logged = False
            
            return bitrate, rtt, True

        except requests.exceptions.RequestException as e:
            delay = self.get_retry_delay(self.server_retry_count)
            logger.error(f"SRT server connection failed: {e}. Retrying in {delay} seconds...")
            self.server_connected = False
            self.server_retry_count += 1
            self.bitrate_none_logged = False
            return None, None, False

    def _toggle_warning(self, visible):
        """Toggle OBS warning source visibility
        
        Args:
            visible (bool): True=show, False=hide
        """
        try:
            self.ws.call(obsrequests.SetSceneItemEnabled(
                sceneName=self.config["SCENE_NAME"],
                sceneItemId=self._get_source_id(),
                sceneItemEnabled=visible
            ))
        except Exception as e:
            logger.error(f"Error toggling warning visibility: {e}")

    def _get_source_id(self):
        """Get OBS source ID (using cache)
        
        Returns:
            int: Source ID
            
        Raises:
            ValueError: If source not found
        """
        if self.source_id is None:
            try:
                scene_items = self.ws.call(obsrequests.GetSceneItemList(sceneName=self.config["SCENE_NAME"]))
                for item in scene_items.datain["sceneItems"]:
                    if item["sourceName"] == self.config["SOURCE_NAME"]:
                        self.source_id = item["sceneItemId"]
                        return self.source_id
                raise ValueError(f"Source '{self.config['SOURCE_NAME']}' not found in scene")
            except Exception as e:
                logger.error(f"Error getting source ID: {e}")
                raise
        return self.source_id

    def _show_warning_for_duration(self):
        """Optimized warning display and timer management"""
        if self.warning_active:
            return
        
        self.warning_active = True
        current_bitrate = self._fetch_bitrate()[0]
        logger.warning(f"Low bitrate warning - {current_bitrate} kbps (Next alert in: {self.config['COOLDOWN_SECONDS']} seconds)")
        
        try:
            self._toggle_warning(True)
            
            # Reuse timer object
            if hasattr(self, 'warning_timer') and self.warning_timer.is_alive():
                self.warning_timer.cancel()
            
            self.warning_timer = threading.Timer(
                self.config["SOURCE_DISPLAY_TIME"],
                self._hide_warning
            )
            self.warning_timer.daemon = True
            self.warning_timer.start()
            
        except Exception as e:
            logger.error(f"Error occurred while showing warning: {e}")
            self.warning_active = False

    def _hide_warning(self):
        """Separate method for handling warning hide"""
        try:
            self._toggle_warning(False)
            self.warning_active = False
            logger.info(f"Low bitrate warning ended [{self.config['SOURCE_NAME']} hidden]")
        except Exception as e:
            logger.error(f"Error occurred while hiding warning: {e}")

    def _handle_low_bitrate(self, bitrate, rtt):
        """Handle bitrate or RTT issues
        
        Args:
            bitrate (float): Current bitrate
            rtt (float): Current RTT
        """
        current_time = time.time()
        if current_time - self.last_sent_time >= self.config["COOLDOWN_SECONDS"] and not self.warning_active:
            self.warning_active = True
            
            # Create warning message
            warning_reason = []
            if bitrate < self.config["BITRATE_THRESHOLD"]:
                warning_reason.append(f"Low bitrate: {bitrate} kbps")
            if rtt > self.config["RTT_THRESHOLD"]:
                warning_reason.append(f"High RTT: {rtt} ms")
            
            warning_msg = " / ".join(warning_reason)
            logger.warning(f"Stream quality warning - {warning_msg} (Next alert in: {self.config['COOLDOWN_SECONDS']} seconds) [{self.config['SOURCE_NAME']} shown]")
            
            self._toggle_warning(True)
            
            def hide_warning():
                time.sleep(self.config["SOURCE_DISPLAY_TIME"])
                self._toggle_warning(False)
                self.warning_active = False
                logger.info(f"Stream quality warning ended [{self.config['SOURCE_NAME']} hidden]")
            
            threading.Thread(target=hide_warning, daemon=True).start()
            self.last_sent_time = current_time

    def run(self):
        """Main monitoring loop
        - Check bitrate and RTT every 2 seconds
        - Show warning on issues
        - Auto-reconnect on connection loss
        """
        initial_wait_start = None
        
        while True:
            if not self.ensure_obs_connection():
                delay = self.get_retry_delay(self.obs_retry_count - 1)
                time.sleep(delay)
                continue

            bitrate, rtt, server_connected = self._fetch_bitrate()
            
            if not server_connected:
                delay = self.get_retry_delay(self.server_retry_count - 1)
                time.sleep(delay)
                continue
            
            if self.ignore_count == 0 and bitrate is not None:
                self._handle_initial_period()
                initial_wait_start = time.time()
            elif initial_wait_start is not None:
                elapsed_time = time.time() - initial_wait_start
                if elapsed_time >= 15:
                    initial_wait_start = None
                continue
            
            # Handle warning when bitrate or RTT exceeds threshold
            elif bitrate is not None and (bitrate < self.config["BITRATE_THRESHOLD"] or rtt > self.config["RTT_THRESHOLD"]):
                self._handle_low_bitrate(bitrate, rtt)
            
            time.sleep(2)

    def _handle_initial_period(self):
        """Handle initial stabilization period
        - Skip checks for first 15 seconds after stream start
        """
        logger.info("Stream detected. Skipping bitrate checks for the first 15 seconds...")
        self.ignore_count = 1

if __name__ == "__main__":
    try:
        monitor = BitrateMonitor("abc_config.json")
        monitor.run()
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        logger.error(f"Program will exit in 10 seconds.")
        time.sleep(10)
        raise
