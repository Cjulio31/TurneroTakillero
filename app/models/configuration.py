from dataclasses import dataclass


@dataclass
class Configuration:
    hub_url: str = ""
    terminal_id: str = ""
    terminal_name: str = ""
    terminal_location: str = ""
    api_token: str = ""
    hub_timeout: int = 10
    reconnect_interval: int = 5
    serial_port: str = ""
    baudrate: int = 9600
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    serial_transmissions: int = 2
    printer_type: str = ""
    printer_port: str = ""
