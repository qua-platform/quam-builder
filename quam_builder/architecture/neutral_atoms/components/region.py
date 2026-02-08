from typing import Dict, List 
from dataclasses import dataclass, field
from quam.core import quam_dataclass
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse

@quam_dataclass
class RegionRegistry:
    """
    registry for neutral atom regions.

    Attributes:
        regions: Dict[str, List[int]] mapping region names to lists of atom IDs.
        atom_to_region: Dict[int, str] mapping atom IDs to their current region.
    """
    regions: Dict[str, List[int]] = field(default_factory=dict)
    atom_to_region: Dict[int, str] = field(default_factory=dict)

# Initialize module-level registry
registry = RegionRegistry()


@quam_dataclass
class Region(QuantumComponent): 
    #TODO: add method which allows to update the region dimensions (and updates the registry, its center and so on
    x1: float
    y1: float
    x2: float
    y2: float
    channels: List[str]
    center: tuple = field(init=False)   #automatically calculated

    @property
    def name(self) -> str:
        return self.id
    

    def __post_init__(self):
        if self.name in registry.regions:
            raise RuntimeError(f"Region '{self.name}' already exists.")
        registry.regions[self.name] = []

        self.center = ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    @QuantumComponent.register_macro
    def global_h(self, amplitude: float = 0.5, length: int = 40):
        """
        Apply a global Hadamard-like π/2 pulse to all qubits in the region.
        Args:
            region: Name of the region containing qubits
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        # Play it on the OPX channel associated with this region
        # Assume you have a mapping from region -> channel(s)
        channels = [self.parent.parent.get_channel(channel_name) for channel_name in self.channels]
        for ch in channels:
            ch.play("h_pulse")
    
    @QuantumComponent.register_macro
    def global_cz(self, amplitude: float = 5, length: int = 1):
        """
        Apply a global Rydberg CZp pulse to all qubits in the region. Inly close qbit paris will be affected.
        Args:
            region: Name of the region containing qubits
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        # Create the square pulse
        h_pulse = SquarePulse(
            amplitude=amplitude,
            length=length,
        )
        # Play it on the OPX channel associated with this region
        # Assume you have a mapping from region -> channel(s)
        channels = self.channel
        for ch in channels:
            ch.play(h_pulse)

def create_region(name: str):
    """Create a new region if it does not exist."""
    if name in registry.regions:
        raise RuntimeError(f"Region '{name}' already exists.")
    registry.regions[name] = []


def add_atom(atom_id: int, region_name: str):
    """Add an atom to a region."""
    if atom_id in registry.atom_to_region:
        raise RuntimeError(f"Atom {atom_id} is already in region '{registry.atom_to_region[atom_id]}'.")
    if region_name not in registry.regions:
        raise RuntimeError(f"Region '{region_name}' does not exist.")
    registry.regions[region_name].append(atom_id)
    registry.atom_to_region[atom_id] = region_name


def remove_atom(atom_id: int, region_name: str):
    """Remove an atom from a specific region."""

    # Check that the region exists
    if region_name not in registry.regions:
        raise RuntimeError(f"Region '{region_name}' does not exist.")

    # Check that the atom is in some region
    if atom_id not in registry.atom_to_region:
        raise RuntimeError(f"Atom {atom_id} is not in any region.")

    # Make sure the atom is in the region we want to remove it from
    current_region = registry.atom_to_region[atom_id]
    if current_region != region_name:
        raise RuntimeError(
            f"Atom {atom_id} is in region '{current_region}', "
            f"cannot exit region '{region_name}'."
        )

    # Remove atom from region and registry
    registry.regions[region_name].remove(atom_id)
    del registry.atom_to_region[atom_id]

def move_atom(atom_id: int, new_region: str):
    """Move an atom from its current region to a new region."""
    if atom_id not in registry.atom_to_region:
        raise RuntimeError(f"Atom {atom_id} is not in any region.")

    old_region = registry.atom_to_region[atom_id]
    remove_atom(atom_id, old_region)
    add_atom(atom_id, new_region)


def get_region_atoms(region_name: str) -> List[int]:
    """Return the list of atom IDs in a given region."""
    if region_name not in registry.regions:
        raise RuntimeError(f"Region '{region_name}' does not exist.")
    return registry.regions[region_name]