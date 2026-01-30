Randomized Benchmarking (Single-Qubit, Spin Qubits)
===================================================

Overview
--------
This implementation runs single-qubit randomized benchmarking (RB) with an
emphasis on minimizing QUA data memory. Rather than precomputing and storing
all gate sequences, the QUA program generates random Cliffords on the PPU and
uses compact lookup tables to compose Cliffords, apply their native gate
decompositions, and append the inverse Clifford at the end of each sequence.

Native Gate Set
---------------
The RB sequences are compiled into a native gate set that matches the hardware:
- X90, X180: physical rotations (Gaussian pulses)
- Y90, Y180: physical rotations (Gaussian pulses with 90-degree phase shift)
- Z90, Z180, Z270: virtual Z rotations (frame rotations, zero duration)
- Idle: identity (removed from decompositions)

Clifford Table Generation
-------------------------
Clifford lookup tables are generated in
`quam_builder/architecture/quantum_dots/examples/rb_utils.py` by
`build_single_qubit_clifford_tables()`:

1. **Enumerate the group**:
   - Use H and S generators to enumerate the 24 single-qubit Cliffords.
   - Assign each Clifford a stable integer index in the list order.

2. **Composition table**:
   - Build a 24x24 table where `compose[left][right] = left * right`.
   - Store it as a flattened list for QUA indexing:
     `compose_flat[left * 24 + right]`.

3. **Inverse table**:
   - For each Clifford index, store the index of its adjoint.

4. **Native decomposition**:
   - For each Clifford, transpile a single-gate circuit into the basis
     `{rz, sx, x}` and map the resulting instructions to native gate IDs.
   - Store the sequences in a flat list with per-Clifford offsets and lengths.

QUA Execution Flow
------------------
The QUA program in
`quam_builder/architecture/quantum_dots/examples/single_qubit_rb.py`
uses the lookup tables as follows:

1. **Outer loops**: shots -> depth -> circuit.
2. **Random Clifford selection**:
   - For each Clifford in the depth, choose `rand_clifford` using
     `Random.rand_int(num_cliffords)`.
3. **Accumulate total Clifford**:
   - Update `total_clifford` with the composition table:
     `total = compose[rand_clifford * 24 + total]`.
4. **Play decomposition**:
   - Use `decomp_offsets`/`decomp_lengths` to play the native gate sequence
     for `rand_clifford`.
5. **Append inverse Clifford**:
   - After the random Cliffords, apply `inverse[total_clifford]` so the ideal
     sequence returns to |0>.

Memory Efficiency
-----------------
This approach replaces large per-circuit gate arrays with small tables:
- Composition table: 24x24 integers
- Inverse table: 24 integers
- Decomposition table: a few hundred integers total

The memory footprint is effectively constant with respect to the number of
circuits, depths, or shots, so it scales to large RB experiments without
triggering QUA data memory limits.

Results and Analysis
--------------------
The program streams a binary state result per sequence and shot. Analysis is
handled by `SingleQubitRBResult` in `rb_utils.py`, which computes survival
probability and fits an exponential decay to extract the Clifford fidelity.
