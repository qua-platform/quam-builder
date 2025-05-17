from typing import Dict, Optional, TYPE_CHECKING

from quam.core import quam_dataclass
from quam.components import Channel, QuantumComponent, QuamMacro
from quam.components.channels import SingleChannel  # As per user clarification


@quam_dataclass
class VoltageTuningPoint(QuamMacro):
    """
    Defines a specific set of DC voltage levels for a group of channels,
    along with a default duration to hold these voltages.
    """

    voltages: Dict[str, float]  # Maps channel name to its target voltage
    duration: int  # Default duration in ns


class VoltageSequence:
    """
    Manages the generation of a QUA sequence for setting and adjusting DC voltages
    on a set of gate channels.
    """

    def __init__(self, gate_set: "GateSet"):
        """
        Initializes the VoltageSequence.

        Args:
            gate_set: The GateSet instance this sequence will operate on.
        """
        self.gate_set: "GateSet" = gate_set
        self.state_trackers: Dict[str, SequenceStateTracker] = {
            ch_name: SequenceStateTracker(ch_name)
            for ch_name in self.gate_set.channels.keys()
        }

    def go_to_point(
        self,
        name: str,
        duration: Optional[int] = None,
    ):
        """
        Sets the gate voltages to a point predefined in the gate set.

        This method performs a direct step to the target voltages.
        Ramping is not currently implemented in this method.

        Args:
            name: The name of the predefined VoltageTuningPoint.
            duration: Optional. The duration (ns) to hold the voltages.
                If None, the default duration from the VoltageTuningPoint is used.

        Steps:
        1. Retrieve the VoltageTuningPoint macro.
        2. For each channel in the point:
            a. Determine the target voltage.
            b. Calculate the delta voltage from the current voltage (via state tracker).
            c. Command the channel to play a DC pulse (e.g., "DC_250mV")
               scaled to achieve the delta voltage, with the specified duration.
               (Actual QUA pulse name and scaling factor depend on user's config).
            d. Update the state tracker for the channel (current_level, integrated_voltage).
        """
        # Placeholder for implementation
        # tuning_point: VoltageTuningPoint = self.gate_set.macros.get(name)
        # if not tuning_point:
        #     raise ValueError(f"VoltageTuningPoint '{name}' not found in GateSet.")
        #
        # effective_duration = duration if duration is not None else tuning_point.duration
        #
        # for ch_name, target_voltage in tuning_point.voltages.items():
        #     if ch_name not in self.gate_set.channels:
        #         # Or handle more gracefully depending on desired behavior
        #         raise ValueError(f"Channel '{ch_name}' in point '{name}' not in GateSet.")
        #
        #     tracker = self.state_trackers[ch_name]
        #     channel_obj = self.gate_set.channels[ch_name]
        #
        #     current_v = tracker.current_level
        #     delta_v = target_voltage - current_v
        #
        #     # --- QUA commands would go here ---
        #     # Example (conceptual, actual QUA depends on channel methods/config):
        #     # qua.play("DC_250mV" * amp(delta_v / 0.25), channel_obj.id,
        #     #          duration=qua.Cast.to_int(effective_duration / 4)) # Assuming 4ns clock
        #
        #     tracker.current_level = target_voltage
        #     tracker.update_integrated_voltage(target_voltage, effective_duration)
        pass

    def apply_compensation_pulse(self, max_voltage: float = 0.49):
        """
        Applies a compensation pulse to each channel to aim for a zero
        time-averaged voltage.

        The duration is chosen to keep the pulse amplitude at or below max_voltage.

        Args:
            max_voltage: The maximum absolute amplitude for the compensation pulse.
        """
        # Placeholder for implementation
        # For each channel_name, channel_obj in self.gate_set.channels.items():
        #     tracker = self.state_trackers[channel_name]
        #     integrated_v = tracker.integrated_voltage
        #     current_v = tracker.current_level
        #
        #     # Calculate compensation amplitude and duration (logic from previous versions)
        #     # comp_amplitude, comp_duration = calculate_compensation(...)
        #
        #     # --- QUA commands would go here ---
        #     # delta_v_comp = comp_amplitude - current_v
        #     # qua.play("DC_250mV" * amp(delta_v_comp / 0.25), channel_obj.id,
        #     #          duration=qua.Cast.to_int(comp_duration / 4))
        #
        #     tracker.current_level = comp_amplitude
        #     # Integrated voltage is reset by ramp_to_zero, or if compensation
        #     # is considered to perfectly zero the integral up to this point.
        #     # For now, let ramp_to_zero handle the reset.
        pass

    def ramp_to_zero(self, ramp_duration: int):
        """
        Ramps the voltage on all channels in the GateSet to zero.

        Args:
            ramp_duration: The duration (ns) of the ramp to zero.
        """
        # Placeholder for implementation
        # for channel_name, channel_obj in self.gate_set.channels.items():
        #     tracker = self.state_trackers[channel_name]
        #     current_v = tracker.current_level
        #
        #     # --- QUA commands would go here ---
        #     # Example (conceptual):
        #     # if hasattr(channel_obj, 'ramp_dc_to_zero'): # Ideal QUAM method
        #     #     channel_obj.ramp_dc_to_zero(ramp_duration)
        #     # else: # Manual QUA ramp
        #     #     if ramp_duration > 0 and current_v != 0:
        #     #         rate = -current_v / ramp_duration
        #     #         qua.ramp(rate, channel_obj.id, duration=qua.Cast.to_int(ramp_duration / 4))
        #
        #     tracker.current_level = 0.0
        #     tracker.reset_integrated_voltage()
        pass

    def apply_to_config(self, config: dict):
        """
        Ensures that the QUA configuration dictionary contains necessary
        definitions for this voltage sequence to operate.

        Specifically, it checks if each channel in the GateSet has a
        predefined operation (e.g., "DC_250mV") that can be used for
        playing DC voltage steps.

        Note: The actual addition of pulses/waveforms if missing is
        currently left as a TODO, as the mechanism depends on how QUAM
        Channel objects handle programmatic updates to their operations.
        In a typical QUAM workflow, these base operations are often expected
        to be part of the initial system configuration.

        Args:
            config: The QUA configuration dictionary.
        """
        # User is primarily responsible for ensuring config is correct.
        # This method could serve as a helper or validator in the future.
        for channel_name, channel_obj in self.gate_set.channels.items():
            # Example check, assuming a standard operation name convention
            expected_op_name = "DC_250mV"  # Or derive from channel/gateset properties
            if (
                not hasattr(channel_obj, "operations")
                or expected_op_name not in channel_obj.operations
            ):
                print(
                    f"Warning: Channel '{channel_name}' (ID: {channel_obj.id}) "
                    f"does not have a '{expected_op_name}' operation defined. "
                    f"VoltageSequence relies on such an operation."
                )
                # TODO: How to programmatically add a standard DC operation
                # to a QUAM Channel object if it's missing?
                # This depends on QUAM's API. For now, it's a user responsibility.
                # Example:
                # if hasattr(channel_obj, 'define_pulse_operation'):
                #     channel_obj.define_pulse_operation(
                #         name=expected_op_name,
                #         pulse_length_ns=16, # Min duration
                #         waveform_sample=0.25
                #     )
                pass


@quam_dataclass
class GateSet(QuantumComponent):
    """
    Represents a set of gate channels used for voltage sequencing.
    Allows defining named voltage tuning points (macros) for this set.
    """

    # channels: Dict[str, Channel] # Using Channel as a placeholder
    channels: Dict[str, SingleChannel]  # Clarified by user

    def __post_init__(self):
        # Ensure macros dictionary exists, as it's accessed by add_point
        if not hasattr(self, "macros"):
            self.macros: Dict[str, QuamMacro] = {}

    def add_point(self, name: str, voltages: Dict[str, float], duration: int):
        """
        Adds a named voltage tuning point (macro) to this GateSet.

        Args:
            name: The name for this tuning point.
            voltages: A dictionary mapping channel names (keys in self.channels)
                to their target DC voltage (float) for this point.
            duration: The default duration (ns) to hold these voltages.
        """
        # Validate that all channel names in 'voltages' exist in self.channels
        for ch_name in voltages.keys():
            if ch_name not in self.channels:
                raise ValueError(
                    f"Channel '{ch_name}' specified in voltages for point '{name}' "
                    f"is not part of this GateSet."
                )

        # The QuamMacro (VoltageTuningPoint) will be stored in the .macros attribute
        # inherited from QuantumComponent (or defined in __post_init__).
        self.macros[name] = VoltageTuningPoint(voltages=voltages, duration=duration)

    def new_sequence(self) -> "VoltageSequence":
        """
        Creates a new VoltageSequence instance associated with this GateSet.
        """
        return VoltageSequence(self)
