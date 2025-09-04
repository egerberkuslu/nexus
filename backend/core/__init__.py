"""
Core package for Mininet Web Framework
"""

# Import main manager class
from .mininet_manager import MininetManager

# Import existing components
from .stats_collector import NetworkStatsCollector
from .router import Router

# Import controller classes from new structure
from .controllers import (
    BaseControllerManager,
    RyuControllerManager,
    POXControllerManager,
    OsKenControllerManager,
    OpenDaylightControllerManager
)

# Import switch classes from new structure
from .switches import (
    BaseSwitchManager,
    LinuxBridgeSwitch,
    OVSSwitchManager,
    P4SwitchManager,
    SwitchFactory
)

# Import factories
from .factories import ControllerFactory

# Import new modular components
from .managers.topology import TopologyBuilder
from .managers.network import NetworkDiagnostics
from .managers.devices import DeviceManager
from .managers.configuration import ConfigurationTracker

# Import LLM components
from .llm import LLMFactory, LLMManager, TopologyLLMService

__all__ = [
    # Main classes (new orchestrator with backward compatibility)
    'MininetOrchestrator',
    'MininetManager',  # Backward compatibility alias

    # Existing components
    'NetworkStatsCollector',
    'Router',

    # Controller classes
    'BaseControllerManager',
    'RyuControllerManager',
    'POXControllerManager',
    'OsKenControllerManager',
    'OpenDaylightControllerManager',

    # Switch classes
    'BaseSwitchManager',
    'LinuxBridgeSwitch',
    'OVSSwitchManager',
    'P4SwitchManager',

    # Factories
    'ControllerFactory',
    'SwitchFactory',

    # New modular components
    'TopologyBuilder',
    'NetworkDiagnostics',
    'DeviceManager',
    'ConfigurationTracker',
    
    # LLM components
    'LLMFactory',
    'LLMManager',
    'TopologyLLMService'
]