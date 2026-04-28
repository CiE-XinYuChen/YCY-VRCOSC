"""command_types.py - Command type definitions and priority ordering."""

from enum import Enum


class CommandType(Enum):
    GUI_COMMAND = 0          # Highest priority — UI sliders
    PANEL_COMMAND = 1        # SoundPad button input
    INTERACTION_COMMAND = 2  # PhysBone / Contact parameter input
