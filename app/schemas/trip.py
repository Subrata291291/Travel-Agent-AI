from typing import List, Literal

from pydantic import BaseModel, Field


class TravelTask(BaseModel):
    """
    A single task that the travel agent needs to perform.
    """

    task_id: str = Field(
        description="Unique identifier for this task."
    )

    task_type: Literal[
        "clarify",
        "weather",
        "transport",
        "hotel",
        "restaurant",
        "itinerary",
        "budget_check",
        "other",
    ]

    description: str

    required: bool = True

    depends_on: List[str] = Field(
        default_factory=list,
        description="Task IDs that must be completed first."
    )


class TravelPlan(BaseModel):
    """
    Structured execution plan created by the planner.
    """

    goal: str

    needs_clarification: bool = False

    clarification_questions: List[str] = Field(
        default_factory=list
    )

    tasks: List[TravelTask] = Field(
        default_factory=list
    )