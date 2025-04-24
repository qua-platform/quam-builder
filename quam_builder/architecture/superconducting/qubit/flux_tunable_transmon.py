from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import FixedFrequencyTransmon
from quam_builder.architecture.superconducting.components.flux_line import FluxLine

__all__ = ["FluxTunableTransmon"]


@quam_dataclass
class FluxTunableTransmon(FixedFrequencyTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:
        z (FluxLine): The z drive component.
        resonator (ReadoutResonator): The readout resonator component.
        freq_vs_flux_01_quad_term (float):
        arbitrary_intermediate_frequency (float):
        phi0_current (float):
        phi0_voltage (float):
    """

    z: FluxLine = None
    freq_vs_flux_01_quad_term: float = 0.0
    arbitrary_intermediate_frequency: float = 0.0
    phi0_current: float = 0.0
    phi0_voltage: float = 0.0
