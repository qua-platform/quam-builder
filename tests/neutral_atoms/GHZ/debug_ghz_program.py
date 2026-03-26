
# Single QUA script generated at 2026-03-26 09:52:39.220091
# QUA library version: 1.2.5


from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    play("slm_on", "SLM532")
    align("SLM532")
    align()
    play(ramp(0.01), "ch1", duration=50)
    play(ramp(0.01), "ch2", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    align()
    play(ramp(-0.02), "ch1", duration=50)
    play(ramp(-0.02), "ch2", duration=50)
    play("h_pulse", "ch5")
    align()
    play(ramp(0.02), "ch1", duration=50)
    play(ramp(0.02), "ch2", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    align()
    play(ramp(-0.02), "ch1", duration=50)
    play(ramp(-0.02), "ch2", duration=50)
    play(ramp(0.0), "ch1", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    play(ramp(0.0), "ch1", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    align()
    play("h_pulse", "ch8")
    align()
    play(ramp(0.02), "ch1", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    align()
    play("h_pulse", "ch8")
    align()
    play(ramp(0.02), "ch1", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    play(ramp(0.02), "ch1", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    align()
    play(ramp(0.02), "ch1", duration=50)
    play(ramp(0.02), "ch2", duration=50)
    play("move_pulse", "ch1")
    play("move_pulse", "ch2")
    play(ramp(-0.02), "ch1", duration=50)
    play(ramp(-0.02), "ch2", duration=50)
    align()
    play("imaging_pulse", "ch6")
    align()
    play("slm_off", "SLM532")
    align("SLM532")
    align()

config = {
    "version": 1,
    "controllers": {
        "con1": {
            "fems": {
                "1": {
                    "type": "LF",
                    "analog_outputs": {
                        "1": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "2": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "3": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "5": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "6": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "7": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "8": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                        "4": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "mw",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                    },
                    "digital_outputs": {
                        "1": {
                            "inverted": False,
                            "shareable": False,
                            "level": "LVTTL",
                        },
                    },
                },
            },
        },
    },
    "elements": {
        "ch1": {
            "operations": {
                "h_pulse": "ch1.h_pulse.pulse",
                "move_pulse": "ch1.move_pulse.pulse",
                "imaging_pulse": "ch1.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 1),
            },
        },
        "ch2": {
            "operations": {
                "h_pulse": "ch2.h_pulse.pulse",
                "move_pulse": "ch2.move_pulse.pulse",
                "imaging_pulse": "ch2.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 2),
            },
        },
        "SLM532": {
            "operations": {
                "h_pulse": "SLM532.h_pulse.pulse",
                "move_pulse": "SLM532.move_pulse.pulse",
                "imaging_pulse": "SLM532.imaging_pulse.pulse",
                "slm_on": "SLM532.slm_on.pulse",
                "slm_off": "SLM532.slm_off.pulse",
            },
            "digitalInputs": {
                "do1": {
                    "port": ('con1', 1, 1),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            "singleInput": {
                "port": ('con1', 1, 3),
            },
        },
        "ch5": {
            "operations": {
                "h_pulse": "ch5.h_pulse.pulse",
                "move_pulse": "ch5.move_pulse.pulse",
                "imaging_pulse": "ch5.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 5),
            },
        },
        "ch6": {
            "operations": {
                "h_pulse": "ch6.h_pulse.pulse",
                "move_pulse": "ch6.move_pulse.pulse",
                "imaging_pulse": "ch6.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 6),
            },
        },
        "ch7": {
            "operations": {
                "h_pulse": "ch7.h_pulse.pulse",
                "move_pulse": "ch7.move_pulse.pulse",
                "imaging_pulse": "ch7.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 7),
            },
        },
        "ch8": {
            "operations": {
                "h_pulse": "ch8.h_pulse.pulse",
                "move_pulse": "ch8.move_pulse.pulse",
                "imaging_pulse": "ch8.imaging_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1, 8),
            },
        },
        "ch4": {
            "operations": {},
            "singleInput": {
                "port": ('con1', 1, 4),
            },
        },
    },
    "pulses": {
        "const_pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "I": "const_wf",
                "Q": "zero_wf",
            },
        },
        "ch1.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch1.h_pulse.wf",
            },
        },
        "ch1.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch1.move_pulse.wf",
            },
        },
        "ch1.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch1.imaging_pulse.wf",
            },
        },
        "ch2.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch2.h_pulse.wf",
            },
        },
        "ch2.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch2.move_pulse.wf",
            },
        },
        "ch2.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch2.imaging_pulse.wf",
            },
        },
        "SLM532.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "SLM532.h_pulse.wf",
            },
        },
        "SLM532.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "SLM532.move_pulse.wf",
            },
        },
        "SLM532.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "SLM532.imaging_pulse.wf",
            },
        },
        "SLM532.slm_on.pulse": {
            "operation": "control",
            "length": 100,
            "digital_marker": "ON",
            "waveforms": {
                "single": "SLM532.slm_on.wf",
            },
        },
        "SLM532.slm_off.pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "single": "SLM532.slm_off.wf",
            },
        },
        "ch5.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch5.h_pulse.wf",
            },
        },
        "ch5.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch5.move_pulse.wf",
            },
        },
        "ch5.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch5.imaging_pulse.wf",
            },
        },
        "ch6.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch6.h_pulse.wf",
            },
        },
        "ch6.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch6.move_pulse.wf",
            },
        },
        "ch6.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch6.imaging_pulse.wf",
            },
        },
        "ch7.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch7.h_pulse.wf",
            },
        },
        "ch7.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch7.move_pulse.wf",
            },
        },
        "ch7.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch7.imaging_pulse.wf",
            },
        },
        "ch8.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch8.h_pulse.wf",
            },
        },
        "ch8.move_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch8.move_pulse.wf",
            },
        },
        "ch8.imaging_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch8.imaging_pulse.wf",
            },
        },
    },
    "waveforms": {
        "zero_wf": {
            "type": "constant",
            "sample": 0.0,
        },
        "const_wf": {
            "type": "constant",
            "sample": 0.1,
        },
        "ch1.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch1.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch1.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch2.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch2.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch2.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "SLM532.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "SLM532.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "SLM532.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "SLM532.slm_on.wf": {
            "type": "constant",
            "sample": 0.0,
        },
        "SLM532.slm_off.wf": {
            "type": "constant",
            "sample": 0.0,
        },
        "ch5.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch5.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch5.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch6.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch6.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch6.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch7.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch7.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch7.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch8.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch8.move_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch8.imaging_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
    },
    "digital_waveforms": {
        "ON": {
            "samples": [[1, 0]],
        },
    },
    "integration_weights": {},
    "mixers": {},
    "oscillators": {},
}

loaded_config = None


