from typing import Optional, Tuple
from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.tweezer import Tweezer
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import SingleChannel, DigitalOutputChannel
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse


from qm.qua import play, ramp
from qm.qua import QuaArray, declare, assign, if_, update_frequency, declare_struct, receive_from_external_stream, qua_struct, declare_struct , declare
from qm.qua.type_hints import QuaVariable

@quam_dataclass
class AOD(TweezerDriver):
    
    channels: Tuple[SingleChannel, Optional[SingleChannel]]  # (X channel, Y channel)
    frequency_to_move: float  # Frequency shift to move the tweezer position
    offset_frequency: float = 0.0  # Offset frequency for calibration
    f_min: float = 70.0 * 1e6
    f_max: float = 150.0 * 1e6
    max_total_power: float = 1.0  # Maximum total RF power allowed

    def _get_structs(self):
        @qua_struct
        class AOD_Move:
            offsets: QuaArray[int, 16]
            src_center: QuaArray[int, 1]
            dst_center: QuaArray[int, 1]
            duration: QuaArray[int , 1]
            image: QuaArray[bool, 1]

        return {"AOD_Move": AOD_Move}
    
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
        target: tuple[float, float] | None = None,
        length: int = 1,
        tweezer: Optional[Tweezer] = None,
    ):            
        # Convert to frequencies
        dst_center = self.position_to_frequency(target[0], target[1])
        src_center = self.position_to_frequency(tweezer.center[0], tweezer.center[1])
        offsets = [self.position_to_frequency(x, y) for x, y in tweezer.spots - src_center]
        duration = length


        self._runtime_move(offsets=offsets, src_center=src_center, dst_center=dst_center, duration=duration)
               
    @QuantumComponent.register_macro
    def _runtime_move(
        self,
        offsets: QuaArray[int, 16] | None = None,
        src_center: QuaArray[int, 1] | None = None,
        duration: QuaArray[int, 1] | None = None,
        dst_center: QuaArray[int, 1] | None = None,
    ):
        
        chirprate = declare(int)
        assign(chirprate, (dst_center[0] - src_center[0]) / duration[0])
        for i in range(16):
            with if_(~offsets[i]==0):
                update_frequency("AOD_{i}", src_center[0])
                play("move", "AOD_{i}", duration=duration[0], chirp=(chirprate, 'MHz/sec'))

    @QuantumComponent.register_macro
    def get_move(self):
        """
        Get move the tweezer to a new target position.
        Args:
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        next_move = self.parent.parent.receive_from_external_stream("AOD_Move")
        self._runtime_move(next_move.dst_center, next_move.image, next_move.duration, next_move.offsets)
