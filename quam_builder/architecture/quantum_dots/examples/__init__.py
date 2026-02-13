try:
    from .macro_examples import *
except ModuleNotFoundError:
    # Optional examples module may be absent in some environments.
    pass

__all__ = []
if "macro_examples" in globals():
    __all__.extend(macro_examples.__all__)
