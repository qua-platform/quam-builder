import os
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
    atoms = [Atom.create(x=0, y=0), Atom.create(x=1, y=0), Atom.create(x=2, y=0)]
    for i, atom in enumerate(atoms):
        atom.enter_region("prepare")
    return atoms

def init_qpu():
    
    aod_channel_x = SingleChannel(opx_output=("con1", 1), id="ch1")
    aod_channel_y = SingleChannel(opx_output=("con1", 2), id="ch2")

    SLM_channel = DigitalOutputChannel(opx_output=("con1", 3))
    hamammatsu_channel = DigitalOutputChannel(opx_output=("con1", 4))
    
    drive_channel = SingleChannel(opx_output=("con1", 5))
    readout_channel = SingleChannel(opx_output=("con1", 6))
    prepare_channel = SingleChannel(opx_output=("con1", 7))
    entangle_channel = SingleChannel(opx_output=("con1", 8))
    
    channels = [aod_channel_x, aod_channel_y, drive_channel, readout_channel, prepare_channel, entangle_channel]
    digital_channels = [SLM_channel, hamammatsu_channel]
    # Create the square pulse
    for channel in channels:
        channel.operations["h_pulse"] = pulses.SquarePulse(amplitude=0.25, length=1000)    
    qpu = BaseQuamNA(channels=channels)
    
    # -- set QPU default parameters --
    qpu.tweezer_depth = 10
    qpu.scale = 1.0
    qpu.rydberg_distance = 0.2  # in scaled units

    # --- Regions ---
    drive_region = Region(id="drive", channels=[drive_channel], x1=0, y1=0, x2=10, y2=0)
    prepare_region = Region(id="prepare", channels=[prepare_channel], x1=10, y1=0, x2=10, y2=0)
    entangle_region = Region(id="entangle", channels=[entangle_channel], x1=20, y1=0, x2=20, y2=0)
    readout_region = Region(id="readout", channels=[readout_channel], x1=30, y1=0, x2=30, y2=0)
    for region in [drive_region, readout_region, prepare_region, entangle_region]:
        qpu.register_regions(region)

    # -- Driver -- #
    aod = AOD(id="AOD532", channels=(aod_channel_x, aod_channel_y), frequency_to_move=1)
    slm = SLM(id="SLM532", channel=SLM_channel, frequency_to_move=1)
    for driver in [aod, slm]:
        qpu.register_driver(driver)

    # -- Sensors -- #
    hamammatsu = Sensor(id="HAMMAMATSU", channel=hamammatsu_channel)  
    qpu.register_sensor(sensor=hamammatsu)

    return qpu

def ghz_3(qpu):

    # -- Initialize Tweezers --

    # Static array via SLM
    static_array = qpu.create_tweezer(
        spots=[(0, i) for i in range(30)],
        id="static_array",
        drive="SLM532"
    )

    # Dynamic tweezers via AOD
    dynamic_tweezer = qpu.create_tweezer(
        spots=[(0, 0), (1, 0), (2, 0)],
        id="dynamic_tweezer",
        drive="AOD532"
    )

    drive_region = qpu.get_region("drive")
    entangle_region = qpu.get_region("entangle")
        

    # -- Initialize atoms --
    atoms = load_atoms()


    with program() as ghz_program:
        
        slm = qpu.get_driver("SLM532")
        slm.enable() 

        # -- GHZ circuit sequence, macros needs to be implemented --
        dynamic_tweezer.move(target=qpu.get_region("drive").center)
        drive_region.global_h() # Should this be registered as a Channel.operations
        dynamic_tweezer.move(target=qpu.get_region("drive").center) 
        # Dynamic tweezers via AOD
        
        # CZ(0,1) and CZ(0,2)
        initial_postion = atoms[0].position
        a0_tweezer = qpu.create_tweezer(
            spots=[initial_postion],
            name="a0_tweezer",
            drive="AOD532"
        )
        a0_tweezer.move(target=atoms[1].position + ( 0, qpu.rydberg_distance))
        entangle_region.global_cz()
        a0_tweezer.move(target=atoms[1].position + ( 0, qpu.rydberg_distance))
        entangle_region.global_cz()
        a0_tweezer.move(target=initial_postion)

        # Mesurement
        qpu.measure(region="readout", sensor="HAMMAMATSU")

        # -- Optional: disable SLM after usage --
        slm.disable()  # static array pattern turned off

    return ghz_program

def main():
    qpu = init_qpu()
    prog = ghz_3(qpu)
    prog.serialize_qua_program()
    config = qpu.generate_config()
    
    serialize_qua_program(prog, qpu)

    qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4") #Serialize 
    qm = qmm.open_qm(config)

    qmm.clear_all_job_results()

    # Run simulation (longer duration for full circuit)
    simulation_config = SimulationConfig(duration=2000)
    job = qmm.simulate(config, prog, simulation_config)

if __name__ == "__main__":
    main()
