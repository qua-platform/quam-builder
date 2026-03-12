import os
import matplotlib
matplotlib.use("TkAgg")
from qm import QuantumMachinesManager, SimulationConfig
from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from quam_builder.architecture.neutral_atoms.atom import Atom
from quam_builder.architecture.neutral_atoms.components.tweezer import Tweezer
from quam_builder.architecture.neutral_atoms.components.slm import SLM
from quam_builder.architecture.neutral_atoms.components.aod import AOD
from quam_builder.architecture.neutral_atoms.components.sensor import Sensor

from quam_builder.architecture.neutral_atoms.components.region import create_region, Region
from quam.components import pulses

from quam.components import SingleChannel, DigitalOutputChannel
from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from qm.qua import *
from qm.qua import wait
from qm import generate_qua_script
from qm import Program

from quam_builder.architecture.nv_center import qpu
from pathlib import Path


def serialize_qua_program(prog: Program, qpu: BaseQuamNA, path: str | None = None):
    name="ghz_program"
    if path is None:
        file_name = f"debug_{name}.py"
    else:
        file_name = os.path.join(path, f"debug_{name}.py")
    sourceFile = open(file_name, 'w')
    print(generate_qua_script(prog, qpu.generate_config()), file=sourceFile) 
    sourceFile.close()

def load_atoms():
    # For simplicity, we directly create atoms at the desired positions. 
    # In a real scenario, this would involve loading atoms from a MOT and rearranging them into the initial configuration.
    atoms = [Atom.create(x=0, y=0), Atom.create(x=1, y=0), Atom.create(x=2, y=0), Atom.create(x=3, y=0)]
    for i, atom in enumerate(atoms):
        atom.enter_region("prepare")
    return atoms

def init_qpu():
    qpu = BaseQuamNA()

    # LF-FEMs are in slots 5 and 6 on cluster CS_4
    aod_channel_x = SingleChannel(opx_output=("con1", 5, 1), id="ch1")
    aod_channel_y = SingleChannel(opx_output=("con1", 5, 2), id="ch2")

    SLM_digital = DigitalOutputChannel(opx_output=("con1", 5, 1), delay=0, buffer=0)
    SLM_channel = SingleChannel(
        opx_output=("con1", 5, 3), id="SLM532",
        digital_outputs={"do1": SLM_digital}
    )
    hamammatsu_channel = SingleChannel(opx_output=("con1", 5, 4), id="ch4")

    drive_channel = SingleChannel(opx_output=("con1", 5, 5), id="ch5")
    readout_channel = SingleChannel(opx_output=("con1", 5, 6), id="ch6")
    prepare_channel = SingleChannel(opx_output=("con1", 5, 7), id="ch7")
    entangle_channel = SingleChannel(opx_output=("con1", 5, 8), id="ch8")

    # SLM pulses: on has digital marker high, off has no digital marker
    SLM_channel.operations["slm_on"] = pulses.SquarePulse(amplitude=0.0, length=100, digital_marker="ON")
    SLM_channel.operations["slm_off"] = pulses.SquarePulse(amplitude=0.0, length=100)

    channels = [aod_channel_x, aod_channel_y, SLM_channel, drive_channel, readout_channel, prepare_channel, entangle_channel]

    # Create the square pulse
    for channel in channels:
        channel.operations["h_pulse"] = pulses.SquarePulse(amplitude=0.25, length=1000)
        qpu.register_channel(channel)

    # Create the move pulse
    for channel in channels:
        channel.operations["move_pulse"] = pulses.SquarePulse(amplitude=0.25, length=1000)
        qpu.register_channel(channel)

    # -- set QPU default parameters --
    qpu.tweezer_depth = 10
    qpu.scale = 1.0
    qpu.rydberg_distance = 0.2  # in scaled units

    # --- Regions ---
    drive_region = Region(id="drive", channels=[drive_channel.name], x1=0, y1=0, x2=10, y2=0)
    prepare_region = Region(id="prepare", channels=[prepare_channel.name], x1=10, y1=0, x2=10, y2=0)
    entangle_region = Region(id="entangle", channels=[entangle_channel.name], x1=20, y1=0, x2=20, y2=0)
    readout_region = Region(id="readout", channels=[readout_channel.name], x1=30, y1=0, x2=30, y2=0)
    for region in [drive_region, readout_region, prepare_region, entangle_region]:
        qpu.register_regions(region)

    # -- Driver -- #
    aod = AOD(id="AOD532", channels=(aod_channel_x, aod_channel_y), frequency_to_move=1 , f_min=-70.0 * 1e6, f_max=70.0 * 1e6, max_total_power=1.0)
    slm = SLM(id="SLM532", channel_name="SLM532", frequency_to_move=1)
    for driver in [aod, slm]:
        qpu.register_driver(driver)

    # -- Sensors -- #
    hamammatsu = Sensor(id="HAMMAMATSU", channel=hamammatsu_channel)  
    qpu.register_sensor(sensor=hamammatsu)

    return qpu

def ghz_4(qpu):

    # -- Initialize Tweezers --

    # Static array via SLM
    static_array = qpu.create_tweezer(
        spots=[(0, i) for i in range(30)],
        id="static_array",
        drive="SLM532",
        current_powers=[0.5 for _ in range(30)]
    )

    # Dynamic tweezers via AOD
    dynamic_tweezer = qpu.create_tweezer(
        spots=[(0, 0), (1, 0), (2, 0), (3, 0)],
        id="dynamic_tweezer",
        drive="AOD532",
        current_powers=[0.5 for _ in range(4)]

    )

    drive_region = qpu.get_region("drive")
    entangle_region = qpu.get_region("entangle")
        
    # -- Initialize atoms --
    atoms = load_atoms()  # Should return 4 atoms now

    with program() as ghz_program:
        
        # --- Stage 0: SLM On ---
        slm = qpu.get_driver("SLM532")
        slm.on()
        qpu.align()  # wait for SLM to be ready

        # --- Stage 1: Move dynamic tweezers to drive region ---
        dynamic_tweezer.ramp_on(target_power=1.0, duration=50)  # ramp-on before move
        dynamic_tweezer.move(target=drive_region.center)
        qpu.align()
        dynamic_tweezer.ramp_off(duration=50)  # ramp-off after move

        drive_region.global_h()
        qpu.align()  # ensure Hadamard finished

        # --- Stage 2: Move dynamic tweezers to entangle region ---
        dynamic_tweezer.ramp_on(target_power=1.0, duration=50)
        dynamic_tweezer.move(target=entangle_region.center)
        qpu.align()
        dynamic_tweezer.ramp_off(duration=50)

        # --- Stage 3: Entanglement CZ gates ---
        initial_pos = atoms[0].position
        a0_tweezer = qpu.create_tweezer(
            spots=[initial_pos],
            current_powers=[1.0],
            name="a0_tweezer",
            drive="AOD532"
        )

        a0_tweezer2 = qpu.create_tweezer(
            spots=[atoms[2].position],
            current_powers=[1.0],
            name="a0_tweezer2",
            drive="AOD532"
        )

        # Step 1: entangle qubits 0&1 and 2&3 in parallel
        a0_tweezer.ramp_on(target_power=1.0, duration=50)

        x, y = atoms[1].position
        a0_tweezer.move(target=(x, y + qpu.rydberg_distance))
        a0_tweezer.ramp_off(duration=50)
        

        a0_tweezer2.ramp_on(target_power=1.0, duration=50)
        x, y = atoms[3].position
        a0_tweezer2.move(target=(x, y + qpu.rydberg_distance))
        a0_tweezer2.ramp_off(duration=50)

        qpu.align()  # wait for moves

        entangle_region.global_cz() # CZ should not be given the tweezers within the region 
        qpu.align()  # ensure CZs finished

        # Step 2: entangle qubits 1 & 2
        a0_tweezer.ramp_on(target_power=1.0, duration=50)
        x, y = atoms[2].position
        a0_tweezer.move(target=(x, y + qpu.rydberg_distance))
        a0_tweezer.ramp_off(duration=50)
        qpu.align()

        entangle_region.global_cz()
        qpu.align()

        # Step 3: return dynamic tweezers
        a0_tweezer.ramp_on(target_power=1.0, duration=50)
        a0_tweezer.move(target=initial_pos)
        a0_tweezer.ramp_off(duration=50)

        a0_tweezer2.ramp_on(target_power=1.0, duration=50)
        x, y = atoms[2].position
        a0_tweezer2.move(target=(x, y + qpu.rydberg_distance))
        a0_tweezer2.ramp_off(duration=50)

        qpu.align()

        # --- Stage 4: Measurement ---
        dynamic_tweezer.ramp_on(target_power=1.0, duration=50)
        dynamic_tweezer.move(target=qpu.get_region("readout").center)
        dynamic_tweezer.ramp_off(duration=50)
        qpu.align()

        qpu.measure(region="readout", sensor="HAMMAMATSU")
        qpu.align()

        # --- Stage 5: SLM Off ---
        slm.off()
        qpu.align()
        
        return ghz_program

def main():
    qpu = init_qpu()
    prog = ghz_4(qpu)
    config = qpu.generate_config()
    
    # current_folder = Path(__file__).resolve().parent
    # serialize_qua_program(prog, qpu, path=current_folder)

    qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4") #Serialize
    qm = qmm.open_qm(config)

    qmm.clear_all_job_results()

    # Run simulation (longer duration for full circuit)
    simulation_config = SimulationConfig(duration=2000)
    job = qmm.simulate(config, prog, simulation_config)

    # Plot simulation output
    import matplotlib.pyplot as plt


    samples = job.get_simulated_samples()
    samples.con1.plot()
    plt.show()


if __name__ == "__main__":
    main()
