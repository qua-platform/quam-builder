from qm import QuantumMachinesManager, SimulationConfig
from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from quam_builder.architecture.neutral_atoms.atom import Atom
from quam_builder.architecture.neutral_atoms.components.tweezer import Tweezer
from quam_builder.architecture.neutral_atoms.components.slm import slm
from quam_builder.architecture.neutral_atoms.components.aod import AOD

from quam_builder.architecture.neutral_atoms.components.region import create_region, Region


from quam.components import SingleChannel
from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from qm.qua import *
from qm.qua import wait

from quam_builder.architecture.nv_center import qpu

def load_atoms():
    atoms = [Atom.create(x=0, y=0), Atom.create(x=1, y=0), Atom.create(x=2, y=0)]
    for i, atom in enumerate(atoms):
        atom.enter_region("prepare")
    return atoms

def init_qpu():
    
    aod_channel_x = SingleChannel(opx_output=("con1", 1), id="ch1")
    aod_channel_y = SingleChannel(opx_output=("con1", 2), id="ch2")
    SLM_channel = SingleChannel(opx_output=("con1", 3), id="ch3")
    
    qpu = BaseQuamNA(channels=[aod_channel_x, aod_channel_y])
    # -- set QPU default parameters --
    qpu.tweezer_depth = 10

    # --- Regions ---
    drive_region = Region(name="prepare", x1=0, y1=0, x2=10, y2=0)
    readout_region = Region(name="drive", x1=10, y1=0, x2=20, y2=0)
    prepare_region = Region(name="readout", x1=20, y1=0, x2=30, y2=0)
    create_region("prepare") #TODO should be implicit in Region init in my opin
    create_region("drive")
    create_region("readout")
    qpu.register_regions(drive_region, readout_region)

    # -- Driver -- #
    aod = AOD(name="AOD532", channels=(aod_channel_x, aod_channel_y), frequency_to_move=1)
    SLM = slm(name="SLM532", channels=(SLM_channel), frequency_to_move=1) #TODO qpu.register_driver
    qpu.register_regions(drive_region, readout_region)
    
    return qpu

def ghz_3(qpu):

    # -- Initialize Tweezers --

    # Static array via SLM
    static_array = qpu.create_tweezer(
        spots=[(0, i) for i in range(30)],
        name="static_array",
        drive="SLM532"
    )

    # Dynamic tweezers via AOD
    dynamic_tweezer = qpu.create_tweezer(
        spots=[(0, 0), (1, 0), (2, 0)],
        name="dynamic_tweezer",
        drive="AOD532"
    )

    # -- Initialize atoms --
    atoms = load_atoms()


    with program() as ghz_program:
        
        slm = qpu.get_device("SLM532")
        slm.enable() 

        # -- GHZ circuit sequence, macros needs to be implemented --
        qpu.move("GHZ_tweezer", target=qpu.get_region("drive").center)
        qpu.global_h(region="drive", amplitude=0.20, length=40) #should this be registered as a Channel.operations
        qpu.move("GHZ_tweezer", region="drive", region="entangle") #TODO 'move' logic should move to tweezer class.
        qpu.cz(0, 1, region="entangle") #global CZ 
        #qpu.move()
        qpu.cz(0, 2, region="entangle")
        qpu.measure(region="readout")

        # -- Optional: disable SLM after usage --
        slm.disable()  # static array pattern turned off

    return ghz_program

def main():
    qpu = init_qpu()
    prog = ghz_3(qpu)
    config = qpu.generate_config()

    qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4") #Serialize 
    qm = qmm.open_qm(config)

    qmm.clear_all_job_results()

    # Run simulation (longer duration for full circuit)
    simulation_config = SimulationConfig(duration=2000)
    job = qmm.simulate(config, prog, simulation_config)

if __name__ == "__main__":
    main()
