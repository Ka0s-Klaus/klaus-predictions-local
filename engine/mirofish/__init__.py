"""MiroFish: enjambre de agentes con voto ponderado por calibración."""

from engine.mirofish.agents import AGENT_CLASSES, Agent, build_agents
from engine.mirofish.consensus import ConsensusResult, weighted_consensus
from engine.mirofish.swarm import MiroFishSwarm, SwarmError

__all__ = [
    "AGENT_CLASSES",
    "Agent",
    "ConsensusResult",
    "MiroFishSwarm",
    "SwarmError",
    "build_agents",
    "weighted_consensus",
]
