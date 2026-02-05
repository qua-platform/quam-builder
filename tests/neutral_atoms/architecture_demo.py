from quam_builder.architecture.neutral_atoms.atom import Atom
from quam_builder.architecture.neutral_atoms.components.tweezer import Tweezer
from quam_builder.architecture.neutral_atoms.components.region import Region , create_region

# -------------------
# Demo script for neutral atom QPU architecture
# -------------------

# --- Regions ---
drive_region = Region(
    name="drive",
    x1=0, y1=-1,
    x2=10, y2=0,
    channels=["ch1"]
)


readout_region = Region(
    name="readout",
    x1=0, y1=-1,
    x2=10, y2=0,
    channels=["ch1"]
)

# --- Tweezers ---
initial_tweezers = Tweezer(
    name="initial",
    spots=[(0, 0), (1, 0), (2, 0)]
)

final_tweezers = Tweezer(
    name="final",
    spots=[(5, 1), (6, 1), (7, 1)]
)

# --- Atoms ---
atoms = [
    Atom.create(x=0, y=0),
    Atom.create(x=1, y=0),
    Atom.create(x=2, y=0),
]

# Load atoms into initial region and tweezers
for atom, spot in zip(atoms, initial_tweezers.spots):
    atom.update_position(*spot)
    atom.enter_region("drive")
    atom.tweezer_id = initial_tweezers.name

print("Initial atom positions:")
for i, atom in enumerate(atoms):
    print(
        f"Atom {i}: "
        f"({atom.x}, {atom.y}), "
        f"Tweezer: {atom.tweezer_id}"
    )


# -------------------
# Transport stage
# -------------------

# Logical transport: atoms follow tweezers
for atom, spot in zip(atoms, final_tweezers.spots):
    atom.tweezer_id = final_tweezers.name
    atom.update_position(*spot)

    atom.exit_region("drive")
    atom.enter_region("readout")


print("Final atom positions:")
for i, atom in enumerate(atoms):
    print(
        f"Atom {i}: "
        f"({atom.x}, {atom.y}), "
        f"Tweezer: {atom.tweezer_id}"
    )
