from qm import DictQuaConfig, QuantumMachinesManager
from qm.qua import *
import numpy as np

import os
from pathlib import Path
import matplotlib
matplotlib.use("TkAgg")

from qm import generate_qua_script
from qm import Program
from qm import QuantumMachinesManager, SimulationConfig
from qm.qua import *

from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from quam_builder.architecture.neutral_atoms.atom import Atom
from quam_builder.architecture.neutral_atoms.components.tweezer import Tweezer
from quam_builder.architecture.neutral_atoms.components.slm import SLM
from quam_builder.architecture.neutral_atoms.components.aod import AOD
from quam_builder.architecture.neutral_atoms.components.sensor import Sensor
from quam_builder.architecture.neutral_atoms.components.region import Region

from quam.components import pulses

from quam.components import SingleChannel, DigitalOutputChannel


def serialize_qua_program(prog: Program, qpu: BaseQuamNA, path: str | None = None, name: str = "program"):
    """
    Optional: Serialize a QUA program into a QUA script, for debugging and verification.

    Args:
        prog (Program): The QUA program to serialize.
        qpu (BaseQuamNA): The QPU object used to generate the hardware configuration.
        path (str | None): Optional directory to save the file. If None, the file
                           is saved in the current working directory.

    Output:
        A Python file (debug_{name}.py) containing the generated QUA script.

    Notes:
        - Useful for verifying pulse sequences and timing at the QUA level.
        - Helps debugging mismatches between high-level QUAM logic and OPX execution.
    """
    if path is None:
        file_name = f"debug_{name}.py"
    else:
        file_name = os.path.join(path, f"debug_{name}.py")
    sourceFile = open(file_name, 'w')
    print(generate_qua_script(prog, qpu.generate_config()), file=sourceFile) 
    sourceFile.close()


def init_qpu():
    """
    Initialize a universal QPU configuration for neutral atom experiments.

    This function sets up:
      - All analog/digital channels
      - Predefined pulses for operations (H, move, imaging)
      - Regions for driving, entanglement, preparation, and readout
      - Drivers (AOD, SLM) and their parameters
      - Sensors (e.g., Hamamatsu camera)

    The resulting QPU object is fully configured for compilation of
    high-level programs and can be reused across multiple experiments.

    Returns:
        BaseQuamNA: Configured QPU object ready for QUAM program compilation.
    """
    
    # Instantiate QPU object
    qpu = BaseQuamNA()

    # Define physical channels
    aod_channel_x = SingleChannel(opx_output=("con1", 1, 1), id="ch1")
    aod_channel_y = SingleChannel(opx_output=("con1", 1, 2), id="ch2")

    SLM_digital = DigitalOutputChannel(opx_output=("con1", 1, 1), delay=0, buffer=0)
    SLM_channel = SingleChannel(
        opx_output=("con1", 1, 3), id="SLM532",
        digital_outputs={"do1": SLM_digital}
    )
    hamammatsu_channel = SingleChannel(opx_output=("con1", 1, 4), id="ch4")

    drive_channel = SingleChannel(opx_output=("con1", 1, 5), id="ch5")
    readout_channel = SingleChannel(opx_output=("con1", 1, 6), id="ch6")

    prepare_channel = SingleChannel(opx_output=("con1", 1, 7), id="ch7")
    entangle_channel = SingleChannel(opx_output=("con1", 1, 8), id="ch8")

    channels = [aod_channel_x, aod_channel_y, SLM_channel,
                 drive_channel, readout_channel, prepare_channel, entangle_channel]

    #  Define qpu analog pulses and register tp each channel.
    for channel in channels:
        channel.operations["h_pulse"] = pulses.SquarePulse(amplitude=0.25, length=1000)
        channel.operations["move_pulse"] = pulses.SquarePulse(amplitude=0.3, length=200)
        channel.operations["imaging_pulse"] = pulses.SquarePulse(amplitude=0.4, length=700)
        qpu.register_channel(channel)

    # SLM pulses: on has digital marker high, off has no digital marker
    SLM_channel.operations["slm_on"] = pulses.SquarePulse(amplitude=0.0, length=100, digital_marker="ON")
    SLM_channel.operations["slm_off"] = pulses.SquarePulse(amplitude=0.0, length=100)
    
    # -- set QPU default parameters --
    qpu.tweezer_depth = 10
    qpu.scale = 1.0
    qpu.rydberg_distance = 0.2  # in scaled units

    # --- Declare Regions ---
    drive_region = Region(id="drive", channels=[drive_channel.name], x1=0, y1=0, x2=10, y2=0)
    prepare_region = Region(id="prepare", channels=[prepare_channel.name], x1=10, y1=0, x2=10, y2=0)
    entangle_region = Region(id="entangle", channels=[entangle_channel.name], x1=20, y1=0, x2=20, y2=0)
    readout_region = Region(id="readout", channels=[readout_channel.name], x1=30, y1=0, x2=30, y2=0)
    for region in [drive_region, readout_region, prepare_region, entangle_region]:
        qpu.register_regions(region)

    # -- Declare Tweezer Drivers -- #
    aod = AOD(id="AOD532", channels=(aod_channel_x, aod_channel_y), frequency_to_move=1 , f_min=-70.0 * 1e6, f_max=70.0 * 1e6, max_total_power=1.0)
    slm = SLM(id="SLM532", channel_name="SLM532", frequency_to_move=1)

    for driver in [aod, slm]:
        qpu.register_driver(driver)

    # -- Declare Sensors -- #
    hamammatsu = Sensor(id="HAMMAMATSU", channel=hamammatsu_channel)  
    qpu.register_sensor(sensor=hamammatsu)



    return qpu

def feedback(qpu):
    # Dynamic tweezers via AOD
    dynamic_tweezer = qpu.create_tweezer(
        spots=[(0, 0), (1, 0), (2, 0), (3, 0)],
        drive="AOD532",
        current_powers=[0.5 for _ in range(4)]
    )
    drive_region = qpu.get_region("drive")
    entangle_region = qpu.get_region("entangle")
    
    qpu.register_structs()
    
    with program() as prog:

        qpu.declare_structs()  # Declare all registered structs from init_qpu
        
        
        # init coold atom positions and imaging settings
        stop = declare(bool)
        assign(stop, False)
        with while_(stop):
            qpu.run_next_command()  # receive next command and route to correct region/driver
            dynamic_tweezer.get_move()
    
    returnprog
        


opx_ip = "172.16.33.114"
cluster_name = "CS_4"
fem_index = 5

config: DictQuaConfig = {
    "controllers": {
        "con1": {
            "fems": {
                fem_index: {
                    "analog_inputs": {},
                    "analog_outputs": {1: {"offset": 0.0}},
                    "digital_inputs": {},
                    "digital_outputs": {'1': {}},
                    "type": "LF"
                },
            }
        }
    },
    "digital_waveforms": {'ON': { 'samples': [(1, 0)], },},
    "elements": {
        "qe1": {
            "intermediate_frequency": 1e6,
            "operations": {"analog": "qe1_analog_pulse", "digital": "digital_pulse"},
            "singleInput": {"port": ("con1", fem_index, 1)},
            "digitalInputs": {
                "digital": {
                    "port": ('con1', fem_index, 1),
                    "delay": 4,
                    "buffer": 0,
                },
            }
        }
    },
    "integration_weights": {},
    "mixers": {},
    "oscillators": {},
    "pulses": {
        "qe1_analog_pulse": {
            "length": 2000,
            "operation": "control",
            "waveforms": {"single": "qe1_analog_pulse_wf_I"},
        },
        'digital_pulse': {
            'length': 16,
            'operation': 'control',
            'digital_marker': 'ON',
            'waveforms': {'single': 'const_zero'}
        }
    },
    "version": 1,
    "waveforms": {"qe1_analog_pulse_wf_I": {"sample": 0.5, "type": "constant"},
                  'const_zero': {'sample': 0.0, 'type': 'constant'}}
}

def main():
    qpu = init_qpu()
    prog = feedback(qpu)
    config = qpu.generate_config()

    current_folder = Path(__file__).resolve().parent
    serialize_qua_program(prog, qpu, path=current_folder, name="feedback_program")

if __name__ == "__main__":
    main()