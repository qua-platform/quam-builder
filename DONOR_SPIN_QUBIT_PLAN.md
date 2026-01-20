# Plan: Extending QuAM Builder for Donor Spin Qubits in Silicon

## Executive Summary

This document outlines a plan to extend the existing `quam_builder` framework to support **donor spin qubits in silicon**, as demonstrated in Andrea Morello's research at UNSW. The architecture shares significant commonalities with the existing Loss-DiVincenzo (LD) quantum dots implementation but requires new abstractions for donor-specific physics including nuclear spin qubits, SET-based readout, and ESR/NMR control.

---

## 1. Background: Donor Spin Qubits vs Quantum Dot Qubits

### 1.1 Key Physical Differences

| Aspect | Quantum Dots (LD) | Donor Spin Qubits |
|--------|-------------------|-------------------|
| **Qubit host** | Gate-defined electrostatic potential | Atomic donor (³¹P in Si) |
| **Confinement** | Tunable via voltage gates | Fixed atomic potential |
| **Qubit encoding** | Electron spin only | Electron spin + Nuclear spin |
| **Two-qubit coupling** | Barrier-controlled exchange | Proximity-based exchange (J~32 MHz) |
| **Readout** | Sensor dot (RF-SET/charge sensing) | SET spin-to-charge conversion |
| **Single-qubit gates** | EDSR (electric dipole) | ESR (magnetic, via antenna) |
| **Nuclear spin** | Not used | Quantum memory / flip-flop qubit |
| **Coherence times** | T2 ~ 1-100 μs | T2 > 30 seconds (nuclear) |
| **Fabrication** | Lithographic gates | Ion implantation / STM patterning |

### 1.2 Donor Device Architecture (Morello Group)

A typical donor spin qubit device comprises:

1. **MOS Platform**: SiO₂ dielectric (~8nm) on isotopically enriched ²⁸Si epilayer
2. **Electrostatic Gates**: 4+ gates controlling donor electrochemical potential
3. **Single-Electron Transistor (SET)**: Charge sensor for spin-to-charge conversion
4. **Microwave Antenna**: On-chip broadband transmission line for ESR/NMR
5. **Implanted Donors**: ³¹P atoms ~10nm beneath oxide surface

### 1.3 Control Mechanisms

| Control Type | Purpose | Implementation |
|--------------|---------|----------------|
| **ESR** | Electron spin rotation | MW antenna, B₁ field at ~40 GHz |
| **NMR** | Nuclear spin rotation | RF pulses at ~24-68 MHz |
| **EDSR** | Flip-flop transitions | Electric field modulation |
| **Voltage pulses** | Charge state control, readout | Gate voltage sequences |
| **Exchange (J)** | Two-qubit gates | Fixed by donor proximity |

### 1.4 Two-Qubit Gate Strategy

Unlike LD qubits where exchange is controlled by barrier gates, donor qubits operate in the **weak-exchange regime** (J < A, where A~100 MHz is hyperfine coupling). A **CROT (Controlled-Rotation) gate** is achieved by a simple ESR π-pulse when nuclear spins are antiparallel, without requiring dynamic J control.

---

## 2. Analysis: Code Reuse Opportunities

### 2.1 Fully Reusable Components (No Changes Needed)

| Component | Location | Reason |
|-----------|----------|--------|
| `VoltageGate` | `components/voltage_gate.py` | Donor gates use same DC control |
| `GateSet` | `components/gate_set.py` | Voltage preset management is identical |
| `VirtualGateSet` | `components/virtual_gate_set.py` | Virtualization for orthogonal control |
| `VirtualDCSet` | `components/virtual_dc_set.py` | External DC source management |
| `VirtualizationLayer` | `components/virtual_gate_set.py` | Matrix transformations |
| `VoltagePointMacroMixin` | `components/macros/mixin.py` | Macro system |
| `StepPointMacro` | `components/macros/step_point_macro.py` | Instant voltage changes |
| `RampPointMacro` | `components/macros/ramp_point_macro.py` | Voltage ramps |
| `SequenceMacro` | `components/macros/sequence_macro.py` | Composite operations |
| `VoltageSequence` | `components/voltage_sequence.py` | QUA program generation |
| `VoltageTuningPoint` | `components/voltage_tuning_point.py` | Named voltage presets |

### 2.2 Adaptable Components (Minor Modifications)

| Component | Location | Required Changes |
|-----------|----------|------------------|
| `XYDrive` | `components/channels/xy_drive.py` | Add ESR-specific pulse shapes (chirped, adiabatic) |
| `ReadoutResonator` | `components/channels/readout_resonator.py` | Adapt for SET readout characteristics |
| `BaseQuamQD` | `qpu/base_quam_qd.py` | Create `BaseQuamDonor` subclass |

### 2.3 New Components Required

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `Donor` | Single donor atom representation | Medium |
| `DonorPair` | Exchange-coupled donor pair | Medium |
| `DonorElectronQubit` | Electron spin qubit | Medium |
| `DonorNuclearQubit` | Nuclear spin qubit (quantum memory) | Medium |
| `FlipFlopQubit` | Combined electron-nuclear qubit | High |
| `SET` | Single-electron transistor readout | Medium |
| `MicrowaveAntenna` | ESR/NMR drive line | Low |
| `NMRChannel` | Nuclear spin control channel | Medium |
| `ESRChannel` | Electron spin resonance channel | Low (extend XYDrive) |

---

## 3. Proposed Architecture

### 3.1 Directory Structure

```
quam_builder/architecture/donor_spins/
├── __init__.py
├── components/
│   ├── __init__.py
│   ├── donor.py                    # Donor atom representation
│   ├── donor_pair.py               # Exchange-coupled donors
│   ├── set_readout.py              # SET charge sensor
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── esr_channel.py          # ESR drive (extends XYDrive)
│   │   ├── nmr_channel.py          # NMR control channel
│   │   └── edsr_channel.py         # EDSR for flip-flop
│   └── gates/
│       ├── __init__.py
│       ├── donor_gate.py           # Gate electrode over donor
│       └── reservoir_gate.py       # Electron reservoir control
├── qpu/
│   ├── __init__.py
│   ├── base_quam_donor.py          # Root container
│   └── donor_qpu.py                # Full donor QPU
├── qubit/
│   ├── __init__.py
│   ├── electron_spin_qubit.py      # Electron spin qubit
│   ├── nuclear_spin_qubit.py       # Nuclear spin qubit
│   └── flip_flop_qubit.py          # Flip-flop qubit
├── qubit_pair/
│   ├── __init__.py
│   └── donor_qubit_pair.py         # Two-qubit system
└── examples/
    ├── __init__.py
    ├── donor_qpu_example.py
    ├── single_donor_qubit.py
    └── two_qubit_crot.py
```

### 3.2 Class Hierarchy

```
QuamRoot
└── BaseQuamDonor
    ├── physical_channels: Dict[str, VoltageGate]      # Reuse
    ├── virtual_gate_sets: Dict[str, VirtualGateSet]   # Reuse
    ├── donors: Dict[str, Donor]                       # New
    ├── donor_pairs: Dict[str, DonorPair]              # New
    ├── sets: Dict[str, SET]                           # New (SET readout)
    ├── esr_channels: Dict[str, ESRChannel]            # New
    ├── nmr_channels: Dict[str, NMRChannel]            # New
    ├── electron_qubits: Dict[str, ElectronSpinQubit]  # New
    ├── nuclear_qubits: Dict[str, NuclearSpinQubit]    # New
    └── flip_flop_qubits: Dict[str, FlipFlopQubit]     # New

Donor (QuamComponent + VoltagePointMacroMixin)
├── id: str
├── species: str  # "P", "As", "Sb"
├── implant_depth: float  # nm
├── hyperfine_coupling: float  # MHz (A parameter)
├── gate_electrodes: List[VoltageGate]
├── electron_qubit: ElectronSpinQubit
├── nuclear_qubit: NuclearSpinQubit
└── charge_state: int  # 0 (ionized) or 1 (neutral)

ElectronSpinQubit (Qubit + VoltagePointMacroMixin)
├── donor: Donor
├── esr_channel: ESRChannel
├── larmor_frequency: float  # GHz
├── T1, T2_ramsey, T2_echo: float
└── set_readout: SET

NuclearSpinQubit (Qubit + VoltagePointMacroMixin)
├── donor: Donor
├── nmr_channel: NMRChannel
├── nuclear_frequency: float  # MHz
├── T1, T2: float  # Very long coherence
└── hyperfine_shift: float  # Frequency shift from electron state

FlipFlopQubit (Qubit + VoltagePointMacroMixin)
├── donor: Donor
├── edsr_channel: EDSRChannel
├── transition_frequency: float
└── electric_dipole_moment: float

SET (QuamComponent)
├── id: str
├── readout_channel: ReadoutResonator  # Reuse from quantum_dots
├── tunnel_rate: float
├── charging_energy: float
├── readout_thresholds: Dict[str, float]
└── spin_up_signature: str  # "blip" detection

DonorPair (QuamComponent + VoltagePointMacroMixin)
├── donor_control: Donor
├── donor_target: Donor
├── exchange_coupling: float  # J in MHz
├── set_readout: SET
└── crot_frequency: float  # Conditional rotation frequency
```

---

## 4. Detailed Component Specifications

### 4.1 Donor Component

```python
@quam_dataclass
class Donor(QuamComponent, VoltagePointMacroMixin):
    """
    Represents a single donor atom (e.g., ³¹P) in silicon.

    Unlike quantum dots, donors have fixed atomic potentials.
    Control is via gate electrodes that tune the electrochemical
    potential for charge state manipulation and readout.
    """
    id: str
    species: str = "P"  # Phosphorus-31 default

    # Physical parameters
    implant_depth: float = 10.0  # nm below oxide
    hyperfine_coupling: float = 117.53  # MHz for ³¹P

    # Associated gates (voltage control)
    gate_electrodes: List[str] = field(default_factory=list)  # References

    # Qubit references (populated after registration)
    electron_qubit: Optional[str] = None  # Reference to ElectronSpinQubit
    nuclear_qubit: Optional[str] = None   # Reference to NuclearSpinQubit

    # State tracking
    charge_state: int = 1  # 1 = neutral (bound electron), 0 = ionized

    # Inherited from mixin
    macros: Dict[str, QuamMacro] = field(default_factory=dict)
    points: Dict[str, str] = field(default_factory=dict)
```

### 4.2 ESR Channel

```python
@quam_dataclass
class ESRChannel(MWChannel):
    """
    Electron Spin Resonance control channel via microwave antenna.

    Extends MWChannel with ESR-specific pulse types including
    chirped adiabatic pulses for frequency identification.
    """
    # ESR-specific parameters
    rabi_frequency: float = 0.0  # MHz, calibrated
    chirp_bandwidth: float = 6.0  # MHz for adiabatic inversion

    # Default pulses
    add_default_pulses: bool = True

    def __post_init__(self):
        super().__post_init__()
        if self.add_default_pulses:
            self._add_esr_pulses()

    def _add_esr_pulses(self):
        """Add ESR-specific pulse shapes."""
        # Standard π pulse
        self.add_pulse("pi", ...)
        # Chirped adiabatic inversion
        self.add_pulse("adiabatic_pi", ...)
        # Gaussian for spectroscopy
        self.add_pulse("spectroscopy", ...)
```

### 4.3 SET Readout

```python
@quam_dataclass
class SET(QuamComponent):
    """
    Single-Electron Transistor for spin-to-charge conversion readout.

    Donor electron spin state is read via energy-dependent tunneling
    to the SET island. Spin-up electrons have sufficient energy to
    tunnel at the charge boundary, producing a detectable current blip.
    """
    id: str

    # Tunnel coupling
    tunnel_rate: float = 0.0  # Hz
    charging_energy: float = 0.0  # meV

    # Readout channel (can reuse ReadoutResonator infrastructure)
    readout_channel: str = None  # Reference

    # Calibration
    readout_fidelity: float = 0.0
    spin_up_threshold: float = 0.0  # Current threshold for spin-up
    integration_time: float = 0.0  # μs

    # Operating point (gate voltages for optimal sensitivity)
    operating_point: Dict[str, float] = field(default_factory=dict)

    def measure_spin(self, donor: Donor) -> ...:
        """Perform spin-to-charge conversion measurement."""
        ...
```

### 4.4 NMR Channel

```python
@quam_dataclass
class NMRChannel(SingleChannel):
    """
    Nuclear Magnetic Resonance control for nuclear spin qubits.

    Operates at much lower frequencies than ESR (~24-68 MHz for ³¹P)
    and requires different pulse shaping for selective addressing.
    """
    nuclear_frequency: float = 0.0  # MHz

    # Frequency depends on electron state (hyperfine shift)
    frequency_electron_up: float = 0.0
    frequency_electron_down: float = 0.0

    # Default pulses
    add_default_pulses: bool = True

    def _add_nmr_pulses(self):
        """Add NMR-specific pulse shapes."""
        self.add_pulse("pi", ...)
        self.add_pulse("pi_half", ...)
        # Selective pulses for multi-donor systems
        self.add_pulse("selective_pi", ...)
```

---

## 5. Implementation Phases

### Phase 1: Core Infrastructure (Foundation)

**Goal**: Establish base donor components with voltage control

**Tasks**:
1. Create `quam_builder/architecture/donor_spins/` directory structure
2. Implement `Donor` component (extend `VoltagePointMacroMixin`)
3. Implement `DonorGate` (electrode over donor, reuse `VoltageGate` patterns)
4. Implement `SET` readout component
5. Create `BaseQuamDonor` QPU root class
6. Write unit tests for core components

**Reuses**: `VoltageGate`, `VirtualGateSet`, `VoltagePointMacroMixin`, all macro classes

### Phase 2: Qubit Abstractions

**Goal**: Implement electron, nuclear, and flip-flop qubit classes

**Tasks**:
1. Implement `ElectronSpinQubit` (similar to `LDQubit`)
2. Implement `NuclearSpinQubit` (new, for quantum memory)
3. Implement `FlipFlopQubit` (combined electron-nuclear)
4. Create registration methods in `BaseQuamDonor`
5. Implement coherence time tracking and thermal reset

**Reuses**: `Qubit` base class from QUAM, `VoltagePointMacroMixin`

### Phase 3: Control Channels

**Goal**: Implement ESR, NMR, and EDSR control channels

**Tasks**:
1. Implement `ESRChannel` extending `MWChannel`/`XYDrive`
2. Implement `NMRChannel` for nuclear control
3. Implement `EDSRChannel` for flip-flop control
4. Add ESR-specific pulse shapes (chirped adiabatic, etc.)
5. Add NMR-specific selective pulses

**Reuses**: `XYDrive`, `MWChannel`, pulse infrastructure

### Phase 4: Two-Qubit Operations

**Goal**: Support exchange-coupled donor pairs

**Tasks**:
1. Implement `DonorPair` component
2. Implement `DonorQubitPair` for two-qubit gates
3. Add CROT gate implementation (ESR π-pulse in weak exchange)
4. Add conditional resonance frequency tracking
5. Implement nuclear spin configuration management

**Reuses**: `QuantumDotPair` patterns, macro system

### Phase 5: Examples and Integration

**Goal**: Demonstrate full workflow with examples

**Tasks**:
1. Create `donor_qpu_example.py` (basic setup)
2. Create `single_donor_qubit.py` (single qubit operations)
3. Create `two_qubit_crot.py` (two-qubit gate)
4. Create wiring example for donor devices
5. Integration tests with simulated hardware

---

## 6. Detailed Code Mapping

### 6.1 What to Reuse Directly (Import)

```python
# In donor_spins/components/__init__.py
from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    GateSet,
    VirtualGateSet,
    VirtualDCSet,
    VirtualizationLayer,
    VoltageSequence,
    VoltageTuningPoint,
)

from quam_builder.architecture.quantum_dots.components.macros import (
    VoltagePointMacroMixin,
    StepPointMacro,
    RampPointMacro,
    SequenceMacro,
    ConditionalMacro,
)
```

### 6.2 What to Extend

```python
# ESRChannel extends XYDrive
from quam_builder.architecture.quantum_dots.components.channels import XYDrive

@quam_dataclass
class ESRChannel(XYDrive):
    """ESR-specific extensions."""
    chirp_bandwidth: float = 6.0  # MHz
    ...

# BaseQuamDonor extends pattern from BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

@quam_dataclass
class BaseQuamDonor(QuamRoot):
    """Similar structure but donor-specific collections."""
    ...
```

### 6.3 What to Write Fresh

| Component | Reason |
|-----------|--------|
| `Donor` | New physics (atomic potential, hyperfine) |
| `NuclearSpinQubit` | No equivalent in quantum dots |
| `FlipFlopQubit` | Unique to donors |
| `SET` | Different readout mechanism |
| `NMRChannel` | Lower frequency, different pulses |
| `DonorPair` | Exchange via proximity, not barrier |

---

## 7. Key Differences in Usage

### 7.1 Initialization Comparison

**Quantum Dots (Current)**:
```python
machine = BaseQuamQD(...)
machine.register_quantum_dots(["qd_0", "qd_1"], virtual_gate_set)
machine.register_barrier_gates(["barrier_01"], virtual_gate_set)
machine.register_sensor_dots(["sd_0"], virtual_gate_set, readout_resonator)
ld_qubit = LDQubit(quantum_dot=machine.quantum_dots["qd_0"], xy_channel=xy_drive)
```

**Donors (Proposed)**:
```python
machine = BaseQuamDonor(...)
machine.register_donors(["P1", "P2"], gate_electrodes, virtual_gate_set)
machine.register_set_readouts(["set_0"], readout_channel)
electron_qubit = ElectronSpinQubit(donor=machine.donors["P1"], esr_channel=esr)
nuclear_qubit = NuclearSpinQubit(donor=machine.donors["P1"], nmr_channel=nmr)
```

### 7.2 Two-Qubit Gate Comparison

**Quantum Dots (Barrier-controlled exchange)**:
```python
# Ramp barrier to turn on exchange
qubit_pair.barrier_gate.ramp_to_point("exchange_on", ramp_duration=100)
# Wait for CZ accumulation
wait(cz_duration)
# Ramp barrier off
qubit_pair.barrier_gate.ramp_to_point("exchange_off", ramp_duration=100)
```

**Donors (Fixed exchange, conditional rotation)**:
```python
# Exchange is always on (J ~ 32 MHz fixed)
# CROT via conditional ESR pulse
if nuclear_config == "antiparallel":
    # Apply π-pulse at conditional frequency
    esr_channel.play("pi", frequency=crot_frequency)
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

- `test_donor.py`: Donor creation, charge state, hyperfine
- `test_electron_spin_qubit.py`: ESR control, coherence tracking
- `test_nuclear_spin_qubit.py`: NMR control, frequency shifts
- `test_set_readout.py`: Spin-to-charge conversion
- `test_donor_pair.py`: Exchange coupling, CROT

### 8.2 Integration Tests

- `test_donor_qpu.py`: Full QPU instantiation
- `test_voltage_sequences.py`: Macro execution
- `test_two_qubit_gate.py`: CROT gate workflow

---

## 9. Timeline and Priorities

### High Priority (Core Functionality)
1. `Donor` component
2. `ElectronSpinQubit`
3. `ESRChannel`
4. `SET` readout
5. `BaseQuamDonor`

### Medium Priority (Full System)
6. `NuclearSpinQubit`
7. `NMRChannel`
8. `DonorPair`
9. `DonorQubitPair`

### Lower Priority (Advanced Features)
10. `FlipFlopQubit`
11. `EDSRChannel`
12. STM-patterning workflow support
13. Multi-donor arrays

---

## 10. References

### Key Papers
1. Morello et al., "Donor Spins in Silicon for Quantum Technologies" (2020)
2. Mądzik et al., "Precision tomography of a three-qubit donor quantum processor" (2022)
3. He et al., "Conditional quantum operation of two exchange-coupled single-donor spin qubits" (2021)
4. Savytskyy et al., "An electrically driven single-atom flip-flop qubit" (2023)

### UNSW Research Group
- https://www.unsw.edu.au/research/fqt/our-research/donor-spin-qubit-in-silicon

---

## Appendix A: Parameter Reference

### Phosphorus-31 in Silicon

| Parameter | Value | Notes |
|-----------|-------|-------|
| Hyperfine coupling (A) | 117.53 MHz | Electron-nuclear |
| Electron g-factor | 1.9985 | |
| Nuclear g-factor | 2.263 | |
| Typical ESR frequency | ~40 GHz | At B ~ 1.4 T |
| Typical NMR frequency | ~24-68 MHz | Depends on electron state |
| Electron T2 (²⁸Si) | > 0.5 s | Isotopically pure |
| Nuclear T2 (²⁸Si) | > 30 s | Extremely long |
| Typical exchange (J) | 10-100 MHz | Depends on separation |

### Other Donor Species (Future)

| Species | Nuclear spin | Hyperfine (MHz) | Notes |
|---------|--------------|-----------------|-------|
| ³¹P | 1/2 | 117.53 | Standard |
| ⁷⁵As | 3/2 | 198.35 | Higher A |
| ¹²¹Sb | 5/2 | 186.80 | Qudit potential |
| ¹²³Sb | 7/2 | 101.52 | 8-level system |
| ²⁰⁹Bi | 9/2 | 1475.4 | Very high A |
