# QUAM Architecture: Neutral Atoms Components (`quam_builder.architecture.neutral_atoms`)

This directory defines the Python classes representing the components of a Quantum Abstract Machine (QUAM) architecture specifically designed for **neutral atom quantum computing systems**. These classes model the physical elements (atoms, regions, tweezers) and serve as the building blocks assembled by the `quam_builder.builder` module to create a complete QUAM configuration object for controlling neutral atom platforms.

The neutral atom architecture is uniquely designed to handle the dynamic nature of neutral atom systems, where qubits can be transported across the device, loaded into and removed from traps, and manipulated with spatially-targeted laser pulses.

## Architecture Overview

The neutral atoms architecture is organized into three core components:

### 1. Region Component

A **region** represents a spatially-defined area where laser pulses can be targeted and applied to atoms.

#### Key Properties

- **Spatial Definition**: Regions are defined by rectangular coordinates **(x1, y1) - (x2, y2)** representing the upper-left and bottom-right corners. Future support for other geometric shapes (e.g., circles) may be added as platform capabilities evolve.

- **Dynamic Coordinates**: Region coordinates can change during circuit execution, allowing for dynamic manipulation and reconfiguration of the control landscape.

- **Channel Association**: Regions are assigned one or more **QUA channels**, which drive the lasers that point to that region. This allows precise control over which physical hardware elements are active for operations on a given region.

- **Dynamic Qubit Association**: Regions maintain a **live list of atoms** that enter and exit the region during circuit execution. At any given time, an atom may be associated with one or more regions. This association must be represented as a **QUA vector** that can be dynamically manipulated in real time, enabling runtime adaptation to changing atom configurations.

#### Usage

Regions act as the primary interface between the control system and the physical atoms:
- When performing operations on a region, **all atoms associated with that region are driven**.
- Atoms retain their association with regions even during transport operations (for lattice-based regions).

---

### 2. Atom Component

An **atom** represents a single neutral atom in the system, with its own spatial position and association to one or more regions.

#### Key Properties

- **Dynamic Coordinates**: Each atom has **(x, y)** coordinates that change dynamically throughout circuit execution. These coordinates must be represented as **QUA variables** to enable real-time manipulation and transport operations.

- **Region Association**: An atom is associated with zero (if lost) or more regions at any given time:
  - During normal operation, an atom is associated with one or more regions.
  - When an atom is lost (escapes from the system), its associated regions become zero.
  - Optional mechanism: A "garbage" region can be defined to track lost atoms by updating their coordinates to `null`.

- **Channel Independence**: Unlike other architectures, **atoms are not directly associated with channels**. Only **regions** are associated with channels. This decoupling allows atoms to move freely without requiring dynamic channel reconfiguration.

- **Transport Support**: The architecture supports transporting atoms between regions. During transport, atoms maintain their operational state while moving to new spatial locations.

#### Operational Semantics

- When a laser pulse is played to a region, only the **atoms currently associated with that region** are affected.
- Atoms can be picked up and transported as individual units or in groups (via a **transporter** concept that can move multiple qubits at once).

---

### 3. Tweezer Component

A **tweezer** is a trap element that confines neutral atoms at specific spatial locations. Represents a "logical" tweezer trapping neutral atoms.
    A Tweezer can consist of many physical spots (e.g., for 2D arrays), but we treat it as a single logical entity for control purposes.

#### Key Properties

- **Array of Spots**: A tweezer is fundamentally a **one / two-dimensional array of spots** with fixed positions.The positions are specified as a **qua list of coordinates**.

- **Center of Mass Motion**: All spots in a tweezer array move together as a unit—there is no relative motion between spots. The **center of mass** of the entire array can be moved via a **chirp trajectory** (a list of chirp rates that define the temporal evolution of the tweezer position).

- **Power Ramping**: Tweezers support **power ramping** via ramp waveforms, allowing gradual transitions in laser intensity for smooth atom loading, unloading, and manipulation.

#### Use Cases

- **Atom Loading**: Tweezers can be positioned and powered up to load atoms into specific locations.
- **Atom Transport**: Tweezers can move (via center-of-mass motion) to transport trapped atoms across the device.
- **Gate Operations**: Tweezers apply laser pulses (via FM, AM, and phase modulation) to perform quantum gates and manipulations.
- **Rearrangement**: Multiple tweezers can be used to dynamically reconfigure the spatial arrangement of atoms.

