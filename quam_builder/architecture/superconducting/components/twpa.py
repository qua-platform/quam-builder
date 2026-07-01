from quam.core import quam_dataclass
from quam import QuamComponent
from typing import Union, Optional, Any
from qm.qua._scope_management.scopes_manager import scopes_manager
from .xy_drive import XYDriveMW, XYDriveIQ

__all__ = ["TWPA"]


@quam_dataclass
class TWPA(QuamComponent):
    """
    QuAM component for a Traveling-Wave Parametric Amplifier (TWPA).

    Each TWPA has a pump channel implemented as two elements on the same physical
    output: ``pump`` (sticky, for continuous output) and ``pump_`` (non-sticky, for
    calibration). Optionally, an isolation channel with ``isolation`` (sticky) and
    ``isolation_`` (non-sticky) on one physical output.

    Attributes
    ----------
    id : int or str
        TWPA identifier. Used for the component name (string as-is, int gets a
        default prefix).
    pump : XYDriveIQ or XYDriveMW
        Pump channel, sticky element, used for continuous pump output.
    pump_ : XYDriveIQ or XYDriveMW
        Pump channel, non-sticky element, used for TWPA calibration.
    isolation : XYDriveIQ or XYDriveMW, optional
        Isolation channel, sticky element. Present only if the TWPA has isolation.
    isolation_ : XYDriveIQ or XYDriveMW, optional
        Isolation channel, non-sticky element. Present only if the TWPA has isolation.
    settling_time : int
        Pump settling time in ns. Default 100.
    pump_frequency : float, optional
        Calibrated pump frequency for maximum average SNR improvement.
    pump_amplitude : float
        Calibrated pump amplitude for maximum average SNR improvement. Default 1.0.
    isolation_frequency : float, optional
        Calibrated isolation tone frequency in Hz.
    isolation_amplitude : float
        Calibrated isolation tone amplitude. Default 1.0.
    pumpline_attenuation (float):
        attenuation in dB of the pump line from the OPX to the input of the TWPA
    signalline_attenuation (float):
        attenuation in dB on the signal line from the OPX to the input of the TWPA
    grid_location : str, optional
        Grid location for layout/plotting (e.g. "0,1").
    qubits : list, optional
        Qubits whose readout signals are amplified by this TWPA.
    initialization : bool
        If True, use this TWPA in the QUA program (e.g. call initialize). Default True.
    _initialized_prog_scope : Any, optional
        Runtime-only reference to the active QUA program scope in which this TWPA
        was initialized. Not serialized.
    """

    id: Union[int, str]

    pump: Union[XYDriveIQ, XYDriveMW] = None
    pump_: Union[XYDriveIQ, XYDriveMW] = None
    isolation: Union[XYDriveIQ, XYDriveMW] = None
    isolation_: Union[XYDriveIQ, XYDriveMW] = None

    settling_time: int = 100
    pump_frequency: float = None
    pump_amplitude: float = 1
    isolation_frequency: float = None
    isolation_amplitude: float = 1

    pumpline_attenuation: float = None
    signalline_attenuation: float = None

    grid_location: str = None
    qubits: list = None

    initialization: bool = True
    _initialized_prog_scope: Optional[Any] = None
    _skip_attrs = ["_initialized_prog_scope"]

    @property
    def name(self):
        """The name of the twpa"""
        return self.id if isinstance(self.id, str) else f"twpa{self.id}"

    def initialize(self, isolation: bool = False):
        """
        Set the TWPA pump (and optionally isolation) to the calibrated tones for the QUA program.

        Has no effect if :attr:`initialization` is False. Each instance is initialized
        at most once per active ``program()`` block; further calls in the same block
        return immediately. Sets the pump frequency from :attr:`pump_frequency` and
        :attr:`pump_amplitude`, then plays the pump operation. If ``isolation`` is
        True and this TWPA has isolation channels, also sets and plays the isolation
        tone from :attr:`isolation_frequency` and :attr:`isolation_amplitude`.

        Parameters
        ----------
        isolation : bool, optional
            If True, also configure and play the isolation tone. Use when the TWPA
            has isolation and you want it active. Default False.

        Notes
        -----
        Initialization state is tracked in :attr:`_initialized_prog_scope` keyed to the
        active QUA program scope object, so the pump is turned on only once per program
        compilation while each new ``program()`` block re-initializes.
        """
        # dont use twpa for the QUA program if initialization is set to False
        if not self.initialization:
            return

        current_program_scope = scopes_manager.program_scope
        if self._initialized_prog_scope is current_program_scope:
            return
        self._initialized_prog_scope = current_program_scope

        if self.pump_frequency is not None:
            self.pump.update_frequency(int(self.pump_frequency - self.pump.LO_frequency))
        if self.pump_amplitude is not None:
            self.pump.play("pump", amplitude_scale=self.pump_amplitude)
        else:
            self.pump.play("pump")

        if isolation:
            if self.isolation_frequency is not None:
                self.isolation.update_frequency(
                    int(self.isolation_frequency - self.isolation.LO_frequency)
                )
            if self.isolation_amplitude is not None:
                self.isolation.play("pump", amplitude_scale=self.isolation_amplitude)
            else:
                self.isolation.play("pump")
