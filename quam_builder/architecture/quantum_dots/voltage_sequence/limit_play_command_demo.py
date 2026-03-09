from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    VirtualGateSet,
)

from quam.components import BasicQuam
from quam.components.ports import OPXPlusAnalogOutputPort
from quam.components.channels import StickyChannelAddon

machine = BasicQuam()

channel_num = 10

for i in range(channel_num):
    ch = VoltageGate(
        id=f"ch{i+1}",
        opx_output=OPXPlusAnalogOutputPort("con1", i + 1),
        sticky=StickyChannelAddon(duration=1000, digital=False),
    )
    machine.channels[f"ch{i+1}"] = ch

vgs = VirtualGateSet(
    id="vgs", channels={name: ch_obj.get_reference() for name, ch_obj in machine.channels.items()}
)
matrix = [
    [1, 0.1, 0.3, 0.4, 0.3],
    [0.2, 1, 0.5, 0.6, 0.2],
    [0.3, 0.4, 1, 0.7, 0.3],
    [0.4, 0.5, 0.6, 1, 0.4],
    [0.3, 0.2, 0.4, 0.5, 1],
]
num_tested_gates = 5

vgs.add_layer(
    source_gates=[f"v_ch{i+1}" for i in range(num_tested_gates)],
    target_gates=[f"ch{i+1}" for i in range(num_tested_gates)],
    matrix=matrix,
)

import numpy as np

voltages = np.linspace(0, 0.1, 1000)
dv = voltages[1] - voltages[0]


from qm.qua import *

seq = vgs.new_sequence(track_integrated_voltage=True, limit_play_commands=True)
with program() as prog:
    base_var = declare(fixed)
    qua_vars = {f"v_ch{i+1}": declare(fixed) for i in range(num_tested_gates)}

    with for_(base_var, voltages[0], base_var < voltages[-1], base_var + dv):
        for i in range(num_tested_gates):
            assign(qua_vars[f"v_ch{i+1}"], base_var)
        # This command should not set physical outputs of 5, 6, 7, 8, 9, 10, if limit_play_commands is True
        seq.step_to_voltages({"v_ch1": qua_vars[f"v_ch1"]}, duration=1000)

        seq.ramp_to_zero()


from qm import QuantumMachinesManager, SimulationConfig

host_ip = "172.16.33.101"
cluster = "CS_1"
qmm = QuantumMachinesManager(host=host_ip, cluster_name=cluster)

simulate = True
# my_compiler_options = CompilerOptionArguments(flags=['not-strict-timing'])
if simulate:
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=50_000 // 4)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
    job = qmm.simulate(machine.generate_config(), prog, simulation_config)
    # Get the simulated samples
    samples = job.get_simulated_samples()
    # Plot the simulated samples
    samples.con1.plot()
    # Get the waveform report object
    waveform_report = job.get_simulated_waveform_report()
    # Cast the waveform report to a python dictionary
    waveform_dict = waveform_report.to_dict()
    # Visualize and save the waveform report
    waveform_report.create_plot(samples, plot=True)
else:
    qm = qmm.open_qm(machine.generate_config())
    # Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
    job = qm.execute(prog)
