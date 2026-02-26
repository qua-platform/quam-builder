from typing import Union
from quam_builder.architecture.superconducting.cavity.cavity import (
    Cavity,
)
from quam_builder.architecture.superconducting.cavity.cavity_mode import (
    CavityMode,
)

__all__ = [
    *cavity.__all__,
    *cavity_mode.__all__,
]

AnyTransmonPair = Union[Cavity, CavityMode]
