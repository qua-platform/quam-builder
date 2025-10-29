from typing import Dict


from quam.core import quam_dataclass
from quam.components import MWChannel, pulses

__all__ = ["XYDrive"]

@quam_dataclass
class XYDrive(MWChannel):
    """
    Microwave drive channel for EDSR/ESR control of Qubits
    """
    add_default_pulses:bool = True

    def __post_init__(self): 
        super().__post_init__()
        if self.add_default_pulses: 
            if "gaussian" not in self.operations: 
                self.operations["gaussian"] = pulses.GaussianPulse(
                    length = 100, 
                    ampltiude = 0.2, 
                    sigma = 40
                )
            if "pi" not in self.operations:
                self.operations["pi"] = pulses.SquarePulse(
                    length=100,
                    amplitude=0.2
                )
            
            if "pi_half" not in self.operations:
                self.operations["pi_half"] = pulses.SquarePulse(
                    length=50,
                    amplitude=0.2
                )


    def add_pulse(self, name: str, pulse: pulses.Pulse) -> None: 
        """Add or update a pulse in the drive operations"""
        self.operations[name] = pulse

    def get_pulse(self, name: str) -> pulses.Pulse: 
        """Get a pulse from operations"""
        if name not in self.operations: 
            raise ValueError(f"Pulse {name} not found in operations")
        return self.operations[name]
    
