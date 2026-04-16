from typing import List, Tuple
from quam.core import quam_dataclass
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver

@quam_dataclass
class Tweezer(QuantumComponent):
    """
    Represents a "logical" tweezer trapping neutral atoms.
    A Tweezer can consist of many physical spots (e.g., for 2D arrays), but we treat it as a single logical entity for control purposes.
    """

    spots: List[Tuple[float, float]]   # (x, y) positions
    drive: str
    current_powers: list[float]  # current power for each spot

    # freq: fixed        # NCO frequency (Unsure if needed)
    # phase: fixed       # phase accumulator
    # amp: fixed         # envelope scaling
    # oscillator: int    # which NCO to use

    @property
    def name(self) -> str:
        return self.id
    
    @property
    def center(self) -> Tuple[float, float]:
        """Calculate the center position of the tweezer based on its spots."""
        x_coords = [x for x, _ in self.spots]
        y_coords = [y for _, y in self.spots]
        return (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords))

    @property
    def dimension(self) -> int:
        """Infer dimensionality (1D vs 2D)."""
        ys = {y for _, y in self.spots}
        return 1 if len(ys) == 1 else 2
    
    def get_drive(self) -> TweezerDriver:
        return self.parent.parent.get_driver(self.drive)
    

    def __post_init__(self):
        if len(self.spots) == 0:
            raise ValueError("Tweezer must contain at least one spot")

        for x, y in self.spots:
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise TypeError("Tweezer spots must be numeric (x, y) tuples")

    @QuantumComponent.register_macro
    def move(self, target: Tuple[float, float] , amplitude: float = 5, length: int = 1):
        """
        Move the tweezer to a new target position.
        Args:
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        # Play it on the OPX channel associated with this region
        # Assume you have a mapping from region -> channel(s)
        # TODO: pass spots, calc current center
        self.get_drive().move(target_positions=[target])
        
        # update internal state
        self.spots = [target]


    @QuantumComponent.register_macro
    def ramp_on(self, target_power: float, duration: int):

        slopes = [
            (target_power - p)/duration
            for p in self.current_powers
        ]

        self.get_drive().ramp(slopes=slopes, duration=duration)

        self.current_powers = [target_power]*len(self.current_powers)

    @QuantumComponent.register_macro
    def ramp_off(self, duration: int):

        slopes = [
            -p/duration
            for p in self.current_powers
        ]

        self.get_drive().ramp(slopes=slopes, duration=duration)

        self.current_powers = [0]*len(self.current_powers)
