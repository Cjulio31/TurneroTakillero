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
    serial_transmissions: int = 1
    serial_header_1: int = 0x99  # 153: primer byte del paquete serial
    serial_header_2: int = 0x55  # 85: segundo byte del paquete serial
    printer_type: str = ""
    printer_port: str = ""
    print_tickets: bool = True  # False: el turno se envía al serial pero no se imprime tiquete
    theme: str = "light"  # tema de la interfaz: "light" (por defecto) o "dark"
