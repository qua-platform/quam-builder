from qm import DictQuaConfig, QuantumMachinesManager
from qm.qua import * 
from qm.qua import QuaArray, declare, assign, if_, update_frequency
import numpy as np


iterations = 1000
stream_id = 1

@qua_struct
class Move:
    offsets: QuaArray[int, 16]
    src_center: QuaArray[int, 1]
    dst_center: QuaArray[int, 1]
    duration: QuaArray[int, 1]
    image: QuaArray[bool, 1]
    
with program() as prog:
    inc_struct = declare_struct(Move)
    # out_struct = declare_struct(Move)

    inc_stream = declare_external_stream(Move, stream_id, QuaStreamDirection.INCOMING)
    # out_stream = declare_external_stream(Move, stream_id, QuaStreamDirection.OUTGOING)

    with infinite_loop_():
        receive_from_external_stream(inc_stream, inc_struct)
        update_frequency("AOD_X", inc_struct.src_center)
        chirprate = declare(int)
        assign(chirprate, (inc_struct.dst_center - inc_struct.src_center) / inc_struct.duration)
        for i in range(16):
             with if_(inc_struct.offsets[i] != 0):
                play("move", "AOD_{i}", duration=inc_struct.duration, chirp=(chirprate, 'MHz/sec'))
        with if_(inc_struct.image):
            play("imaging", "imaging_channel")
            play("camera_trigger", "camera_trigger_channel")


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
