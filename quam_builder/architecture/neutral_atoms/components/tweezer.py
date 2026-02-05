from typing import List, Tuple
from quam.core import quam_dataclass

@quam_dataclass
class Tweezer:
    """
    Represents a tweezer trapping neutral atoms.
    """

    spots: List[Tuple[float, float]]   # (x, y) positions
    name: str | None = None 
    # freq: fixed        # NCO frequency (Unsure if needed)
    # phase: fixed       # phase accumulator
    # amp: fixed         # envelope scaling
    # oscillator: int    # which NCO to use

    def __post_init__(self):
        if len(self.spots) == 0:
            raise ValueError("Tweezer must contain at least one spot")

        for x, y in self.spots:
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise TypeError("Tweezer spots must be numeric (x, y) tuples")

    @property
    def dimension(self) -> int:
        """Infer dimensionality (1D vs 2D)."""
        ys = {y for _, y in self.spots}
        return 1 if len(ys) == 1 else 2
