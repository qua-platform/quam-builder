from typing import Dict

from dataclasses import dataclass , field
from quam.core import QuamRoot, quam_dataclass
from quam.components import QuantumComponent
from qm import qua , program


from quam.components import SingleChannel
from quam.components.channels import Channel

from quam_builder.architecture.neutral_atoms.components import TweezerDriver, Sensor, Region, Tweezer

@quam_dataclass
class  BaseQuamNA(QuamRoot):
    _channels: list = field(default_factory=list)
    tweezer_depth: float = 5.0  # in mK
    scale: float = 1.0  # scaling factor between qum and real space
    rydberg_distance: float = 0.3  # in scaled units
    channel_voltages: Dict[str, float] = field(default_factory=dict)
    _drivers: list[TweezerDriver] = field(default_factory=list)
    _regions: list = field(default_factory=list)
    _sensors: list = field(default_factory=list)
    _tweezers: list = field(default_factory=list)

    def set_voltage(self, voltage: float):
        """
        Set the voltage of the channel.

        Args:
            voltage: voltage value to set
        """
        if hasattr(self.channel, "offset_parameter") and self.channel.offset_parameter is not None:
            self.channel.offset_parameter(voltage)
        self.channel.current_voltage = voltage  # keep track internally
    
    def register_driver(self, driver: TweezerDriver):
        self._drivers = getattr(self, "_drivers", [])
        self._drivers.append(driver)

    def register_sensor(self, sensor: Sensor):
        self._sensors = getattr(self, "_sensors", [])
        self._sensors.append(sensor)

    def register_regions(self, region: Region):
        self._regions = getattr(self, "_regions", [])
        self._regions.append(region)
    
    def register_tweezer(self, tweezer: Tweezer):
        self._tweezers = getattr(self, "_tweezers", [])
        self._tweezers.append(tweezer)
    
    def register_channel(self, channel: Channel):
        self._channels = getattr(self, "_channels", [])
        self._channels.append(channel)

    def create_tweezer(self, spots: list[tuple[float, float]], id: str | None = None, drive: str | None = None) -> Tweezer:
        tweezer = Tweezer(spots=spots, id=id, drive=drive)
        self.register_tweezer(tweezer)
        return tweezer

    def get_region(self, name: str):
        for region in self._regions:
            if region.name == name:
                return region
        raise ValueError(f"Region '{name}' not found")

    def get_driver(self, name: str):
        for driver in self._drivers:
            if driver.name == name:
                return driver
        raise ValueError(f"Driver '{name}' not found")

    def get_sensor(self, name: str):
        for sensor in self._sensors:
            if sensor.name == name:
                return sensor
        raise ValueError(f"Sensor '{name}' not found")
    
    def get_channel(self, name: str):
        for channel in self._channels:
            if channel.name == name:
                return channel
        raise ValueError(f"Channel '{name}' not found")
    
    @QuantumComponent.register_macro
    def measure(self, region_name: str, sensor_name: str):
        """
        Measure the signal from the channel for a specific region.

        Args:
            region: Name of the region to measure in

        Returns:
            Measured signal value
        """
        region = self.get_region(region_name)
        sensor = self.get_sensor(sensor_name)


        sensor.trigger()
        region.imaging_pulse(amplitude=0.5, length=100)
        