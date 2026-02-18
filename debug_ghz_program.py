
# Single QUA script generated at 2026-02-18 13:03:46.455112
# QUA library version: 1.2.4


from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch5")
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch8")
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch8")
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch1")
    play("h_pulse", "ch2")
    play("h_pulse", "ch6")

config = {
    "version": 1,
    "controllers": {
        "con1": {
            "analog_outputs": {
                "1": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "2": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "5": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "6": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "7": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "8": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
                "4": {
                    "delay": 0,
                    "shareable": False,
                    "offset": 0.0,
                },
            },
            "digital_outputs": {
                "3": {
                    "inverted": False,
                    "shareable": False,
                },
            },
        },
    },
    "elements": {
        "ch1": {
            "operations": {
                "h_pulse": "ch1.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 1),
            },
        },
        "ch2": {
            "operations": {
                "h_pulse": "ch2.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 2),
            },
        },
        "ch5": {
            "operations": {
                "h_pulse": "ch5.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 5),
            },
        },
        "ch6": {
            "operations": {
                "h_pulse": "ch6.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 6),
            },
        },
        "ch7": {
            "operations": {
                "h_pulse": "ch7.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 7),
            },
        },
        "ch8": {
            "operations": {
                "h_pulse": "ch8.h_pulse.pulse",
            },
            "singleInput": {
                "port": ('con1', 8),
            },
        },
        "ch4": {
            "operations": {},
            "singleInput": {
                "port": ('con1', 4),
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
        "ch2.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch2.h_pulse.wf",
            },
        },
        "ch5.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch5.h_pulse.wf",
            },
        },
        "ch6.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch6.h_pulse.wf",
            },
        },
        "ch7.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch7.h_pulse.wf",
            },
        },
        "ch8.h_pulse.pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "ch8.h_pulse.wf",
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
        "ch2.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch5.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch6.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch7.h_pulse.wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "ch8.h_pulse.wf": {
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


