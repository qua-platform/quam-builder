from typing import Optional, Tuple
from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import SingleChannel, DigitalOutputChannel
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse


from qm.qua import play, ramp

@quam_dataclass
class AOD(TweezerDriver):
    channels: Tuple[SingleChannel, Optional[SingleChannel]]  # (X channel, Y channel)
    frequency_to_move: float  # Frequency shift to move the tweezer position
    offset_frequency: float = 0.0  # Offset frequency for calibration
    f_min: float = 70.0 * 1e6
    f_max: float = 150.0 * 1e6
    max_total_power: float = 1.0  # Maximum total RF power allowed

    @property
    def name(self) -> str:
        return self.id

    @QuantumComponent.register_macro
    def enable(self):
        """Enable the AOD driver."""
        self.channel.current_voltage = 1.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(1.0)

    @QuantumComponent.register_macro
    def disable(self):
        """Disable the AOD driver."""
        self.channel.current_voltage = 0.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(0.0)

    @QuantumComponent.register_macro
    def ramp(self, slopes: list[float], duration: int):

        for ch, slope in zip(self.channels, slopes):
            if ch is not None:
                play(ramp(slope), ch.name, duration=duration)
    
    def position_to_frequency(self, x: float, y: float) -> tuple[float, float]:
        """
        Convert a target tweezer position (x, y) into the AOD frequencies for X and Y channels.
        """
        fx = self.offset_frequency + x * self.frequency_to_move
        fy = self.offset_frequency + y * self.frequency_to_move
        return fx, fy

    def validate_move(self, target_positions: list[tuple[float, float]], amplitudes: list[float] | None = None):
        """
        Validate a list of target positions (x, y) before moving tweezers.
        Converts positions to frequencies internally.
        """
        if len(target_positions) == 0:
            raise ValueError("No target positions provided.")

        # Convert positions to frequencies
        freqs = [self.position_to_frequency(x, y) for x, y in target_positions]

        # --- Frequency range checks ---
        for fx, fy in freqs:
            if not (self.f_min <= fx <= self.f_max):
                raise ValueError(f"X frequency {fx} out of range.")
            if not (self.f_min <= fy <= self.f_max):
                raise ValueError(f"Y frequency {fy} out of range.")

        # # Optional: monotonic ordering
        xs = [fx for fx, _ in freqs]
        ys = [fy for _, fy in freqs]
        if xs != sorted(xs):
            raise ValueError("X frequencies must be ordered.")
        if ys != sorted(ys):
            raise ValueError("Y frequencies must be ordered.")

        # # Optional: total power check
        if amplitudes is not None:
            if sum(amplitudes) > self.max_total_power:
                raise ValueError("Total RF power exceeds limit.")
        
        if amplitudes is not None and len(amplitudes) != len(self.channels):
            raise ValueError(
                "Number of amplitudes must match number of AOD channels."
            )

        return True

    @QuantumComponent.register_macro
    def move(
        self,
        target_positions: list[tuple[float, float]] | None = None,
        target: tuple[float, float] | None = None,
        amplitudes: list[float] | None = None
    ):
        """Move tweezers to a list of target positions (or single target)."""
        if target is not None:
            target_positions = [target]
        if target_positions is None:
            raise ValueError("Must provide either target or target_positions")
        
        # Validate
        self.validate_move(target_positions, amplitudes)
    
        # Convert to frequencies
        target_frequencies = [self.position_to_frequency(x, y) for x, y in target_positions]

        for ch in self.channels:
            if ch is not None:
                ch.play("move_pulse")