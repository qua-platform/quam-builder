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
from qm.qua import *
from qm.qua import wait
from qm import generate_qua_script
from qm import Program

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
    atoms = [Atom.create(x=0, y=0), Atom.create(x=1, y=0), Atom.create(x=2, y=0)]
    for i, atom in enumerate(atoms):
        atom.enter_region("prepare")
    return atoms

def init_qpu():
    qpu = BaseQuamNA()

    aod_channel_x = SingleChannel(opx_output=("con1", 1), id="ch1")
    aod_channel_y = SingleChannel(opx_output=("con1", 2), id="ch2")

    SLM_channel = DigitalOutputChannel(opx_output=("con1", 3))
    hamammatsu_channel = SingleChannel(opx_output=("con1", 4), id="ch4")

    drive_channel = SingleChannel(opx_output=("con1", 5), id="ch5")
    readout_channel = SingleChannel(opx_output=("con1", 6), id="ch6")
    prepare_channel = SingleChannel(opx_output=("con1", 7), id="ch7")
    entangle_channel = SingleChannel(opx_output=("con1", 8), id="ch8")

    # Register all channels in the root channels dict (each channel has exactly one parent).
    # Analog channels (SingleChannel) are registered by their id; the DigitalOutputChannel
    # has no id field so an explicit name is passed.
    analog_channels = [aod_channel_x, aod_channel_y, hamammatsu_channel,
                       drive_channel, readout_channel, prepare_channel, entangle_channel]
    for channel in analog_channels:
        channel.operations["h_pulse"] = pulses.SquarePulse(amplitude=0.25, length=1000)
        qpu.register_channel(channel)
    qpu.register_channel(SLM_channel, name="slm_ch")

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
    # Channels are already registered in qpu.channels, so get_reference() returns the
    # correct QUAM path string. Components store these references rather than the
    # objects themselves, keeping each channel's parent unique.
    aod = AOD(
        id="AOD532",
        channel_x=aod_channel_x.get_reference(),
        channel_y=aod_channel_y.get_reference(),
        frequency_to_move=1,
    )
    slm = SLM(id="SLM532", channel=SLM_channel.get_reference(), frequency_to_move=1)
    for driver in [aod, slm]:
        qpu.register_driver(driver)

    # -- Sensors -- #
    hamammatsu = Sensor(id="HAMMAMATSU", channel=hamammatsu_channel.get_reference())
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

        # Dynamic tweezers via AOD
        dynamic_tweezer.move(target=qpu.get_region("entangle").center)

        # CZ(0,1) and CZ(0,2)
        initial_position = atoms[0].position
        a0_tweezer = qpu.create_tweezer(
            spots=[initial_position],
            name="a0_tweezer",
            drive="AOD532"
        )
        a0_tweezer.move(target=(atoms[1].position[0], atoms[1].position[1] + qpu.rydberg_distance))
        entangle_region.global_cz()
        a0_tweezer.move(target=(atoms[2].position[0], atoms[2].position[1] + qpu.rydberg_distance))
        entangle_region.global_cz()
        a0_tweezer.move(target=initial_position)


        # Mesurement
        dynamic_tweezer.move(target=qpu.get_region("readout").center)
        qpu.measure(region="readout", sensor="HAMMAMATSU")

        # -- Optional: disable SLM after usage --
        slm.disable()  # static array pattern turned off

    return ghz_program

def main():
    qpu = init_qpu()

    qpu.save("quam_state/")

    prog = ghz_3(qpu)

    config = qpu.generate_config()


    # serialize_qua_program(prog, qpu)
    #
    # qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4") #Serialize
    # qm = qmm.open_qm(config)
    #
    # qmm.clear_all_job_results()
    #
    # # Run simulation (longer duration for full circuit)
    # simulation_config = SimulationConfig(duration=2000)
    # job = qmm.simulate(config, prog, simulation_config)
    return config

if __name__ == "__main__":
    config = main()