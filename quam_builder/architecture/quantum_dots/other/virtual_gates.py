import numpy as np
import copy
from qm.qua import (
    program,
    declare,
    assign,
    play,
    fixed,
    Cast,
    amp,
    wait,
    ramp,
    ramp_to_zero,
    Math,
    if_,
    else_,
    stream_,
    save,
    align,
)

# Assuming Scalar and QuaVariable are available from qm.qua.type_hints
# If not, these might need to be aliased to Union types
from qm.qua.type_hints import QuaVariable, Scalar, QuaExpression


from typing import Union, List, Dict, Optional, Tuple, Any, TYPE_CHECKING
from warnings import warn

# --- Import from local modules ---
from ..exceptions import (
    VoltageSequenceError,
    ConfigurationError,
    VoltagePointError,
    TimingError,
    StateError,
)
from ..utils import is_qua_type, validate_duration

if TYPE_CHECKING:
    from ..voltage_sequence.sequence_state_tracker import SequenceStateTracker


# --- Constants ---
# Timing
MIN_PULSE_DURATION_NS = 16
CLOCK_CYCLE_NS = 4
# Compensation Pulse Calculation
INTEGRATED_VOLTAGE_SCALING_FACTOR = 1024  # For fixed-point precision (V*ns*1024)
COMPENSATION_SCALING_FACTOR = 1.0 / INTEGRATED_VOLTAGE_SCALING_FACTOR  # ~0.0009765625
MIN_COMPENSATION_DURATION_NS = 16
# Default duration for compensation pulse when using QUA variables (ns)
DEFAULT_QUA_COMPENSATION_DURATION_NS = 48
# Estimated gap added before QUA compensation pulse calculation (ns)
QUA_COMPENSATION_GAP_NS = 96
# Safety gap subtracted from calculated compensation pulse duration (ns)
COMPENSATION_SAFETY_GAP_NS = 12  # 3 clock cycles
# Default step pulse properties
DEFAULT_STEP_PULSE_NAME = "vg_step_pulse"
DEFAULT_STEP_WF_NAME = "vg_step_wf"
DEFAULT_STEP_AMPLITUDE = 0.25  # Base amplitude (V) for scaling
# Ramp calculation delay approximation (clock cycles)
RAMP_QUA_DELAY_CYCLES = 9


# --- Type Aliases (using Scalar as per user's tracker) ---
VoltageLevelType = Scalar[float]  # Union[float, QuaVariable, QuaExpression]
DurationType = Scalar[int]  # Union[int, QuaVariable, QuaExpression]
ConfigDict = Dict[str, Any]
QuaVarDict = Dict[str, QuaVariable]


# --- ConfigManager Class ---
class ConfigManager:
    """Manages modifications to the QUA configuration dictionary."""

    def __init__(self, initial_config: ConfigDict):
        if not isinstance(initial_config, dict):
            raise ConfigurationError("Initial configuration must be a dictionary.")
        self._config: ConfigDict = copy.deepcopy(initial_config)

    def _generate_unique_name(self, base_name: str, existing_keys: Dict) -> str:
        name = base_name
        while name in existing_keys:
            name += "%"
        return name

    def add_default_step_pulse(self, elements: List[str]):
        if DEFAULT_STEP_PULSE_NAME not in self._config.get("pulses", {}):
            self._config.setdefault("pulses", {})[DEFAULT_STEP_PULSE_NAME] = {
                "operation": "control",
                "length": MIN_PULSE_DURATION_NS,
                "waveforms": {"single": DEFAULT_STEP_WF_NAME},
            }
        if DEFAULT_STEP_WF_NAME not in self._config.get("waveforms", {}):
            self._config.setdefault("waveforms", {})[DEFAULT_STEP_WF_NAME] = {
                "type": "constant",
                "sample": DEFAULT_STEP_AMPLITUDE,
            }
        elements_config = self._config.setdefault("elements", {})
        for el in elements:
            if el not in elements_config:
                raise ConfigurationError(f"Element '{el}' not found in configuration.")
            el_ops = elements_config[el].setdefault("operations", {})
            if "step" not in el_ops:
                el_ops["step"] = DEFAULT_STEP_PULSE_NAME

    def add_constant_pulse(
        self, element: str, base_op_name: str, amplitude: float, length: int
    ) -> str:
        elements_config = self._config.get("elements", {})
        if element not in elements_config:
            raise ConfigurationError(f"Element '{element}' not found.")
        element_ops = elements_config[element].setdefault("operations", {})
        pulses_config = self._config.setdefault("pulses", {})
        waveforms_config = self._config.setdefault("waveforms", {})
        op_name = self._generate_unique_name(f"{element}_{base_op_name}", element_ops)
        pulse_name = self._generate_unique_name(f"{op_name}_pulse", pulses_config)
        wf_name = self._generate_unique_name(f"{op_name}_wf", waveforms_config)
        element_ops[op_name] = pulse_name
        pulses_config[pulse_name] = {
            "operation": "control",
            "length": length,
            "waveforms": {"single": wf_name},
        }
        waveforms_config[wf_name] = {"type": "constant", "sample": amplitude}
        return op_name

    def get_config(self) -> ConfigDict:
        return copy.deepcopy(self._config)

    def check_opx1000_compatibility(self):
        for controller_config in self._config.get("controllers", {}).values():
            if controller_config.get("type") == "opx1000":
                warn(
                    "OPX1000 detected. Ramps in amplified LF-FEM mode may have issues.",
                    UserWarning,
                    stacklevel=3,
                )
                return

    def is_amplified_mode(self, element: str) -> bool:
        try:
            el_conf = self._config["elements"][element]
            ctrl, port, ch = el_conf["singleInput"]["port"]
            ctrl_conf = self._config["controllers"][ctrl]
            if ctrl_conf.get("type") == "opx1000":
                fem_conf = ctrl_conf.get("fems", {}).get(port, {})
                if fem_conf.get("type") == "LF":
                    return (
                        fem_conf.get("analog_outputs", {})
                        .get(ch, {})
                        .get("output_mode")
                        == "amplified"
                    )
        except (KeyError, IndexError, TypeError):
            warn(
                f"Could not determine output mode for '{element}'.",
                UserWarning,
                stacklevel=3,
            )
        return False


# --- VoltagePointManager Class ---
class VoltagePointManager:
    """Manages named voltage points in the gate space."""

    def __init__(self):
        self._voltage_points: Dict[str, Dict[str, Any]] = {}

    def add_point(
        self, name: str, coordinates: List[float], duration: int, num_elements: int
    ):
        if not isinstance(name, str) or not name:
            raise VoltagePointError("Point name must be a non-empty string.")
        if name in self._voltage_points:
            raise VoltagePointError(f"Voltage point '{name}' already exists.")
        if not isinstance(coordinates, list) or not all(
            isinstance(c, (float, int)) for c in coordinates
        ):
            raise VoltagePointError("Coordinates must be a list of numbers.")
        if len(coordinates) != num_elements:
            raise VoltagePointError(
                f"Coordinates length ({len(coordinates)}) must match "
                f"element count ({num_elements})."
            )
        validate_duration(duration, f"duration for point '{name}'")
        if duration != 0:  # Ensure minimum duration if non-zero
            duration = max(duration, MIN_PULSE_DURATION_NS)
        self._voltage_points[name] = {
            "coordinates": [float(c) for c in coordinates],
            "duration": duration,
        }

    def get_point(self, name: str) -> Tuple[List[float], int]:
        if name not in self._voltage_points:
            raise VoltagePointError(f"Voltage point '{name}' not defined.")
        point_data = self._voltage_points[name]
        return point_data["coordinates"], point_data["duration"]


# --- QuaCommandGenerator Class ---
class QuaCommandGenerator:
    """Generates QUA commands for voltage sequence steps, ramps, etc."""

    def __init__(self, config_manager: ConfigManager):
        self._config_manager = config_manager
        self._temp_qua_vars: QuaVarDict = {}

    def _get_temp_qua_var(self, name_suffix: str, var_type=fixed) -> QuaVariable:
        # Ensure unique names for temporary variables
        internal_name = f"_vgs_tmp_{name_suffix}"
        if internal_name not in self._temp_qua_vars:
            self._temp_qua_vars[internal_name] = declare(var_type)
        return self._temp_qua_vars[internal_name]

    def play_step(
        self, element: str, delta_v: VoltageLevelType, duration: DurationType
    ):
        py_duration = 0
        if not is_qua_type(duration):
            py_duration = int(float(str(duration)))

        if is_qua_type(delta_v) or is_qua_type(duration):
            if py_duration == 0 and not is_qua_type(duration):
                return
            scaled_amp = delta_v * (1.0 / DEFAULT_STEP_AMPLITUDE)
            if is_qua_type(duration):
                play(DEFAULT_STEP_PULSE_NAME * amp(scaled_amp), element)
                wait_cycles = (duration - MIN_PULSE_DURATION_NS) >> 2
                with if_(wait_cycles > 0):
                    wait(wait_cycles, element)
            else:  # Fixed duration (py_duration > 0)
                op_name = self._config_manager.add_constant_pulse(
                    element, "step", DEFAULT_STEP_AMPLITUDE, py_duration
                )
                play(op_name * amp(scaled_amp), element)
        else:  # Fixed delta_v and fixed duration
            if py_duration > 0:
                op_name = self._config_manager.add_constant_pulse(
                    element, "const_step", float(str(delta_v)), py_duration
                )
                play(op_name, element)

    def play_ramp(
        self,
        element: str,
        delta_v: VoltageLevelType,
        ramp_duration: DurationType,
        hold_duration: DurationType,
    ):
        if self._config_manager.is_amplified_mode(element):
            warn(
                f"Ramp on amplified element '{element}'. Possible issues.",
                RuntimeWarning,
                stacklevel=4,
            )

        py_ramp_duration = 0
        if not is_qua_type(ramp_duration):
            py_ramp_duration = int(float(str(ramp_duration)))
        ramp_duration_cycles = (
            ramp_duration >> 2 if is_qua_type(ramp_duration) else py_ramp_duration >> 2
        )

        if ramp_duration_cycles > 0:
            if is_qua_type(delta_v) or is_qua_type(ramp_duration):
                ramp_rate = self._get_temp_qua_var(f"{element}_ramp_rate")
                assign(ramp_rate, delta_v * Math.div(1.0, ramp_duration))
                play(ramp(ramp_rate), element, duration=ramp_duration_cycles)
            else:  # Fixed delta_v and fixed ramp_duration
                py_delta_v = float(str(delta_v))
                # py_ramp_duration is already int
                if py_ramp_duration > 0:  # Avoid division by zero
                    ramp_rate = py_delta_v / py_ramp_duration
                    play(ramp(ramp_rate), element, duration=ramp_duration_cycles)

        py_hold_duration = 0
        if not is_qua_type(hold_duration):
            py_hold_duration = int(float(str(hold_duration)))

        if is_qua_type(hold_duration):
            wait_cycles = hold_duration >> 2
            if is_qua_type(ramp_duration):
                wait_cycles -= RAMP_QUA_DELAY_CYCLES
            with if_(wait_cycles > 0):
                wait(wait_cycles, element)
        else:
            if py_hold_duration > 0:
                wait(py_hold_duration >> 2, element)

    def play_compensation_pulse(
        self,
        element: str,
        integrated_voltage: Union[int, QuaVariable],
        current_level: VoltageLevelType,
        max_amplitude: float,
    ) -> Tuple[VoltageLevelType, DurationType]:
        comp_amp_val: VoltageLevelType
        comp_dur_val: DurationType

        if not is_qua_type(integrated_voltage) and not is_qua_type(current_level):
            py_int_v = int(float(str(integrated_voltage)))
            py_curr_v = float(str(current_level))
            if py_int_v == 0:
                return 0.0, 0
            ideal_dur = abs(py_int_v * COMPENSATION_SCALING_FACTOR / max_amplitude)
            py_comp_dur = max(ideal_dur, MIN_COMPENSATION_DURATION_NS)
            py_comp_dur = (
                (int(np.ceil(py_comp_dur)) + CLOCK_CYCLE_NS - 1)
                // CLOCK_CYCLE_NS
                * CLOCK_CYCLE_NS
            )
            py_comp_dur = max(py_comp_dur, DEFAULT_QUA_COMPENSATION_DURATION_NS)

            py_comp_amp = 0.0
            if py_comp_dur > 0:
                py_comp_amp = -(py_int_v * COMPENSATION_SCALING_FACTOR) / py_comp_dur
                py_comp_amp = np.clip(py_comp_amp, -max_amplitude, max_amplitude)

            delta_v = py_comp_amp - py_curr_v
            op_dur = py_comp_dur - COMPENSATION_SAFETY_GAP_NS
            if op_dur >= MIN_PULSE_DURATION_NS:
                op_name = self._config_manager.add_constant_pulse(
                    element, "compensation", delta_v, op_dur
                )
                play(op_name, element)
                if COMPENSATION_SAFETY_GAP_NS > 0:
                    wait(COMPENSATION_SAFETY_GAP_NS >> 2, element)
            else:
                warn(
                    f"Comp pulse for {element} too short ({py_comp_dur}ns). Minimal pulse played.",
                    UserWarning,
                    stacklevel=4,
                )
                self.play_step(element, delta_v, MIN_PULSE_DURATION_NS)
                py_comp_dur = MIN_PULSE_DURATION_NS
            comp_amp_val, comp_dur_val = py_comp_amp, py_comp_dur
        else:
            eval_int_v = self._get_temp_qua_var(f"{element}_eval_int_v", int)
            q_comp_dur_i = self._get_temp_qua_var(f"{element}_comp_dur_i", int)
            q_comp_dur_4ns = self._get_temp_qua_var(f"{element}_comp_dur_4", int)
            q_comp_amp = self._get_temp_qua_var(f"{element}_comp_amp", fixed)
            gap_contrib = Cast.mul_int_by_fixed(
                QUA_COMPENSATION_GAP_NS << 10, current_level
            )
            assign(eval_int_v, integrated_voltage + gap_contrib)
            assign(
                q_comp_dur_i,
                Cast.mul_int_by_fixed(
                    Math.abs(eval_int_v), COMPENSATION_SCALING_FACTOR / max_amplitude
                ),
            )
            with if_(q_comp_dur_i < MIN_COMPENSATION_DURATION_NS):
                assign(q_comp_dur_i, MIN_COMPENSATION_DURATION_NS)
            assign(q_comp_dur_4ns, (q_comp_dur_i + 3) >> 2 << 2)
            with if_(q_comp_dur_4ns < DEFAULT_QUA_COMPENSATION_DURATION_NS):
                assign(q_comp_dur_4ns, DEFAULT_QUA_COMPENSATION_DURATION_NS)
            with if_(eval_int_v == 0):
                assign(q_comp_amp, 0.0)
            with else_():
                with if_(q_comp_dur_4ns > 0):
                    inv_dur = Math.div(1.0, q_comp_dur_4ns)
                    assign(
                        q_comp_amp,
                        -Cast.mul_int_by_fixed(eval_int_v, COMPENSATION_SCALING_FACTOR)
                        * inv_dur,
                    )
                with else_():
                    assign(q_comp_amp, 0.0)
            delta_v_q = q_comp_amp - current_level
            with if_(q_comp_dur_4ns > 0):
                play(
                    DEFAULT_STEP_PULSE_NAME
                    * amp(delta_v_q * (1.0 / DEFAULT_STEP_AMPLITUDE)),
                    element,
                    duration=q_comp_dur_4ns >> 2,
                )
            comp_amp_val, comp_dur_val = q_comp_amp, q_comp_dur_4ns
        return comp_amp_val, comp_dur_val

    def play_ramp_to_zero(
        self, element: str, current_level: VoltageLevelType, duration: Optional[int]
    ):
        if duration is None:
            ramp_to_zero(element)
        else:
            validate_duration(duration, "ramp_to_zero duration")
            py_duration = int(duration)
            if is_qua_type(current_level):
                rate = self._get_temp_qua_var(f"{element}_r2z_rate")
                with if_(py_duration > 0):
                    assign(rate, -current_level * Math.div(1.0, py_duration))
                    play(ramp(rate), element, duration=py_duration >> 2)
            else:
                py_curr_v = float(str(current_level))
                if py_duration > 0 and py_curr_v != 0.0:
                    rate_val = -py_curr_v / py_duration
                    play(ramp(rate_val), element, duration=py_duration >> 2)


# --- VoltageGateSequence Class ---
class VoltageGateSequence:
    """Main class to build and manage voltage gate sequences using QUA."""

    def __init__(self, initial_config: ConfigDict, elements: List[str]):
        if not isinstance(elements, list) or not all(
            isinstance(el, str) for el in elements
        ):
            raise TypeError("`elements` must be a list of strings.")
        if not elements:
            raise ValueError("`elements` list cannot be empty.")
        if len(set(elements)) != len(elements):
            raise ValueError("`elements` list must contain unique names.")

        self._elements = elements
        self._num_elements = len(elements)
        self._config_manager = ConfigManager(initial_config)
        self._point_manager = VoltagePointManager()
        self._command_generator = QuaCommandGenerator(self._config_manager)
        self._trackers: Dict[str, SequenceStateTracker] = {
            name: SequenceStateTracker(name) for name in elements
        }
        self._config_manager.check_opx1000_compatibility()
        self._config_manager.add_default_step_pulse(self._elements)

    def add_points(self, name: str, coordinates: List[float], duration: int):
        self._point_manager.add_point(name, coordinates, duration, self._num_elements)

    def add_step(
        self,
        level: Optional[List[VoltageLevelType]] = None,
        duration: Optional[DurationType] = None,
        voltage_point_name: Optional[str] = None,
        ramp_duration: Optional[DurationType] = None,
    ):
        target_levels_list: List[VoltageLevelType]
        target_duration: DurationType
        if voltage_point_name:
            if level:
                raise VoltagePointError(
                    "Cannot provide both `level` and `voltage_point_name`."
                )
            coords, point_dur = self._point_manager.get_point(voltage_point_name)
            target_levels_list, target_duration = (
                coords,
                duration if duration is not None else point_dur,
            )
        elif level:
            if duration is None:
                raise TimingError("Must provide `duration` with `level`.")
            if not isinstance(level, list) or len(level) != self._num_elements:
                raise ValueError(
                    f"Level list length must match element count ({self._num_elements})."
                )
            target_levels_list, target_duration = level, duration
        else:
            raise VoltagePointError(
                "Must provide either `level` or `voltage_point_name`."
            )

        validate_duration(target_duration, "target_duration")
        validate_duration(ramp_duration, "ramp_duration")
        if ramp_duration and is_qua_type(ramp_duration):
            warn(
                "Using QUA variable for `ramp_duration`. Ensure hold duration is sufficient.",
                UserWarning,
                stacklevel=3,
            )

        for i, el_name in enumerate(self._elements):
            tracker = self._trackers[el_name]
            target_v = target_levels_list[i]
            delta_v = target_v - tracker.current_level  # type: ignore
            tracker.update_integrated_voltage(target_v, target_duration, ramp_duration)
            if ramp_duration is None:
                self._command_generator.play_step(el_name, delta_v, target_duration)
            else:
                valid_ramp_dur = ramp_duration if ramp_duration is not None else 0
                self._command_generator.play_ramp(
                    el_name, delta_v, valid_ramp_dur, target_duration
                )
            tracker.current_level = target_v

    def add_compensation_pulse(self, max_amplitude: float = 0.49):
        if max_amplitude <= 0:
            raise ValueError("`max_amplitude` must be positive.")
        for el_name in self._elements:
            tracker = self._trackers[el_name]
            comp_amp, _ = self._command_generator.play_compensation_pulse(
                el_name,
                tracker.integrated_voltage,
                tracker.current_level,
                max_amplitude,
            )
            tracker.current_level = comp_amp

    def ramp_to_zero(self, duration: Optional[int] = None):
        for el_name in self._elements:
            tracker = self._trackers[el_name]
            self._command_generator.play_ramp_to_zero(
                el_name, tracker.current_level, duration
            )
            tracker.current_level = 0.0
            tracker.reset_integrated_voltage()

    def get_final_config(self) -> ConfigDict:
        return self._config_manager.get_config()


# --- Example Usage (Illustrative) ---
if __name__ == "__main__":
    # This example assumes you have created the following files in the same directory
    # or a package named 'your_package_name' (adjust imports accordingly):
    # your_package_name/
    #  ┣ __init__.py
    #  ┣ exceptions.py (defining StateError, VoltageSequenceError, etc.)
    #  ┣ utils.py (defining is_qua_type, validate_duration)
    #  ┣ sequence_state_tracker.py (defining SequenceStateTracker)
    #  ┗ (this_file.py, containing VoltageGateSequence and other managers)

    # If running this directly and files are in the same dir, relative imports work:
    # from .exceptions import StateError # etc.
    # from .utils import is_qua_type, validate_duration
    # from .sequence_state_tracker import SequenceStateTracker

    # For a standalone run of this example, we'd need to define these locally
    # or adjust sys.path, which is beyond a simple example. The code above
    # assumes these are importable.

    dummy_config = {
        "version": 1,
        "controllers": {
            "con1": {
                "type": "opx1",
                "analog_outputs": {1: {"offset": 0.0}, 2: {"offset": 0.0}},
            }
        },
        "elements": {
            "P1": {
                "singleInput": {"port": ("con1", 1)},
                "operations": {},
                "intermediate_frequency": 0,
            },
            "P2": {
                "singleInput": {"port": ("con1", 2)},
                "operations": {},
                "intermediate_frequency": 0,
            },
        },
        "pulses": {},
        "waveforms": {},
        "digital_waveforms": {},
        "integration_weights": {},
        "mixers": {},
    }
    gate_elements = ["P1", "P2"]
    seq_builder = VoltageGateSequence(copy.deepcopy(dummy_config), gate_elements)
    seq_builder.add_points("idle", coordinates=[-0.1, 0.2], duration=500)
    seq_builder.add_points("load", coordinates=[0.3, -0.15], duration=100)

    with program() as my_prog:
        ramp_time_qua = declare(int, value=40)
        seq_builder.add_step(voltage_point_name="idle")
        seq_builder.add_step(voltage_point_name="load", ramp_duration=20)
        seq_builder.add_step(level=[0.1, 0.15], duration=60)
        seq_builder.add_step(voltage_point_name="load", ramp_duration=ramp_time_qua)  # type: ignore
        seq_builder.add_compensation_pulse(max_amplitude=0.45)
        seq_builder.ramp_to_zero(duration=100)

    final_config = seq_builder.get_final_config()
    print("Example sequence built. Final config (elements section):")
    for el_name in gate_elements:
        print(
            f"  Element {el_name} operations: {final_config['elements'][el_name]['operations']}"
        )
    # In a real scenario, you would now use 'final_config' and 'my_prog'
    # with a QuantumMachinesManager to simulate or run on hardware.
