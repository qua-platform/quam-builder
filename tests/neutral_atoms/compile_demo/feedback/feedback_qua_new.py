from enum import Enum
from qm import DictQuaConfig, QuantumMachinesManager
from qm.qua import * 
from qm.qua import QuaArray, declare, assign, if_, update_frequency
import numpy as np


iterations = 1000
id = 1

class Commands(Enum):
    Move = 0
    Image = 1
    STOP = 255

@qua_struct
class Move:
    offsets: QuaArray[int, 16]
    src_center: QuaArray[int, 1]
    dst_center: QuaArray[int, 1]
    duration: QuaArray[int, 1]

@qua_struct
class Image:
    duration: QuaArray[int, 1]

@qua_struct
class Next_command:
    command: QuaArray[int, 1]

with program() as prog:
    inc_next_command_struct = declare_struct(Next_command)
    inc_move_struct = declare_struct(Move)
    inc_image_struct = declare_struct(Image)

    inc__move_stream = declare_external_stream(Move, id, QuaStreamDirection.INCOMING)
    inc_image_stream = declare_external_stream(Image, id+1, QuaStreamDirection.INCOMING)
    inc_next_command_stream = declare_external_stream(Next_command, id+2, QuaStreamDirection.INCOMING)

    # init coold atom positions and imaging settings
    stop = declare(bool)
    assign(stop, False)
    with while_(stop):
        receive_from_external_stream(inc_next_command_stream, inc_next_command_struct)
        with switch_(inc_next_command_struct.command[0]) as switch:
             with case_(Commands.Move.value):
                 receive_from_external_stream(inc__move_stream, inc_move_struct)
                 update_frequency("AOD_X", inc_move_struct.src_center[0])
                 chirprate = declare(int)
                 assign(chirprate, (inc_move_struct.dst_center[0] - inc_move_struct.src_center[0]) / inc_move_struct.duration[0])
                 for i in range(16):
                     with if_(~inc_move_struct.offsets[i]==0):
                        update_frequency(f"AOD_{i}", inc_move_struct.src_center[0])
                        play("move", f"AOD_{i}", duration=inc_move_struct.duration[0], chirp=(chirprate, 'MHz/sec'))
             with case_(Commands.Image.value):
                receive_from_external_stream(inc_image_stream, inc_image_struct)
                play("imaging", "imaging_channel", duration=inc_image_struct.duration[0])
                play("camera_trigger", "camera_trigger_channel")    
             with case_(Commands.STOP.value):
                assign(stop, True)
    get final timestamp for latency measurement

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

qmm = QuantumMachinesManager(host=opx_ip, cluster_name=cluster_name)

qm = qmm.open_qm(config)
job = qm.execute(prog)
job.result_handles.wait_for_all_values()

latency_start = job.result_handles.get("ts_start").fetch_all(flat_struct=True)
latency_end = job.result_handles.get("ts_end").fetch_all(flat_struct=True)

latency_values = latency_end - latency_start
latency_ns = np.mean(latency_values)
latency_std = np.std(latency_values)
latency_min = np.min(latency_values)
latency_max = np.max(latency_values)

# print(latency_start)
# print(latency_end)
print(f"cpu round trip latency = {latency_ns}[ns]")
print(f"std = {latency_std:.3f}[ns], min = {latency_min:.3f}[ns], max = {latency_max:.3f}[ns]")
