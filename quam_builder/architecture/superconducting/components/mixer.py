from quam.core import quam_dataclass
from quam.components import Mixer


@quam_dataclass
class StandaloneMixer(Mixer):
    @property
    def name(self):
        for name, frequency_converter in self.parent.parent.items():
            if self.parent == frequency_converter:
                return name
        raise KeyError()


__all__ = [
    "StandaloneMixer",
]
