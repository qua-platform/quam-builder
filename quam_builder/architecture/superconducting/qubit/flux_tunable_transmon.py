from typing import Union

from quam_builder.architecture.superconducting.components.flux_line import FluxLine
from quam_builder.architecture.superconducting.components.reset_drive import ResetIQ, ResetMW
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import FixedFrequencyTransmon

from quam.core import quam_dataclass

__all__ = ["FluxTunableTransmon"]


@quam_dataclass
class FluxTunableTransmon(FixedFrequencyTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:
        z (FluxLine): The z drive component.
        resonator (ReadoutResonator): The readout resonator component.
        freq_vs_flux_01_quad_term (float): Quadratic term of the qubit frequency versus flux parabola.
        phi0_current (float): The qubit flux quantum in Ampere.
        phi0_voltage (float): The qubit flux quantum in Volt.
    """

    z: FluxLine = None
    freq_vs_flux_01_quad_term: float = 0.0
    phi0_current: float = 0.0
    phi0_voltage: float = 0.0


@quam_dataclass
class FluxTunableTransmonReset(FluxTunableTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit with reset capabilities.
    """

    f0g1: Union[ResetIQ, ResetMW] = None
