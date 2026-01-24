from typing import Union

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import (
    FluxTunableTransmon,
)
from quam_builder.architecture.superconducting.components.cavity import CavityIQ, CavityMW
from quam_builder.architecture.superconducting.components.side_band import SideBandIQ, SideBandMW

__all__ = ["FluxTunableTransmonCavity", "FluxTunableTransmonCavitySideBand"]



@quam_dataclass
class FluxTunableTransmonCavity(FluxTunableTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:

    """
    alice: Union[CavityIQ, CavityMW] = None
    bob: Union[CavityIQ, CavityMW] = None


@quam_dataclass
class FluxTunableTransmonCavitySideBand(FluxTunableTransmonCavity):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:

    """
    sideband1: Union[SideBandIQ, SideBandMW] = None
    sideband2: Union[SideBandIQ, SideBandMW] = None