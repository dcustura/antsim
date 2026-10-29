"""antsim: NEC2 (nec2c) wire-antenna modelling harness."""
from .model import (ALUMINIUM, COPPER, Component, Feedline, FeedlineChain, Ground, Load, Model, Transformer, Wire,
                    wavelength)
from .wire_gauge import AWG, awg

__all__ = ["ALUMINIUM", "AWG", "COPPER", "Component", "Feedline", "FeedlineChain", "Ground", "Load", "Model",
           "Transformer", "Wire", "awg", "wavelength"]
