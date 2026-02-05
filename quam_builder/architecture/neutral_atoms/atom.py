# atom.py
from typing import Optional
from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.region import add_atom, remove_atom, move_atom

_atom_counter = 0  # simple global counter for unique atom IDs

@quam_dataclass
class Atom:
    """
    Represents a single neutral atom.

    Phase 1 attributes:
        id: unique integer
        x, y: positions (float)
        region_id: name of the region the atom is in (Optional[str])
        shelved: bool, whether the atom is in a shelved state
        alive: bool, True if the atom is present
        tweezer_id: Optional[int], the ID of the tweezer holding this atom
    """

    id: int
    x: float
    y: float
    region_id: Optional[str] = None
    shelved: bool = False
    alive: bool = True
    tweezer_id: Optional[int] = None

    @classmethod 
    def create(cls, x: float, y: float): 
        """Factory method to create a unique Atom instance."""
        global _atom_counter
        atom = cls(id=_atom_counter, x=x, y=y)
        _atom_counter += 1
        return atom

    # -------------------
    # Region operations
    # -------------------
    def enter_region(self, region_name: str):
        """Add atom to a region (updates region registry and region_id)."""
        add_atom(self.id, region_name)
        self.region_id = region_name

    def exit_region(self, region_name: str):
        """Remove atom from a specific region."""
        if self.region_id is None:
            raise RuntimeError(
                f"Atom {self.id} is not in any region."
            )

        if self.region_id != region_name:
            raise RuntimeError(
                f"Atom {self.id} is in region '{self.region_id}', "
                f"cannot exit region '{region_name}'."
            )

        remove_atom(self.id, region_name)
        self.region_id = None


    def move_region(self, new_region: str):
        """Move atom to a new region."""
        move_atom(self.id, new_region)
        self.region_id = new_region

    # -------------------
    # Atom state operations
    # -------------------
    def mark_lost(self):
        """Mark atom as lost/dead."""
        self.alive = False
        # optionally move to a 'garbage' region in the registry
        try:
            self.move_region("garbage")
        except RuntimeError:
            pass

    def shelve(self):
        """Shelve the atom (put it in an internal state)."""
        self.shelved = True

    def unshelve(self):
        """Return atom to normal state."""
        self.shelved = False


    # -------------------
    def update_position(self, x: float, y: float):
        """Update atom position."""
        self.x = x
        self.y = y
