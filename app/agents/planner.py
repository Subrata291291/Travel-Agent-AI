from app.llm.router import LLMRouter
from app.schemas.perception import TripPerception
from app.schemas.trip import TravelPlan


class PlannerAgent:

    def __init__(
        self,
        llm_router: LLMRouter,
    ):
        self.llm_router = llm_router

    def create_plan(
        self,
        perception: TripPerception,
        memory_context: dict | None = None,
    ) -> TravelPlan:

        llm = (
            self.llm_router
            .get_primary_llm()
        )

        structured_llm = (
            llm.with_structured_output(
                TravelPlan,
                method="json_schema",
            )
        )

        if memory_context is None:
            memory_context = {
                "conversation_history": [],
                "user_preferences": [],
                "resolved_destination": None,
            }

        resolved_destination = (
            memory_context.get(
                "resolved_destination"
            )
        )

        prompt = f"""
You are the planning layer of a professional
travel AI agent.

Create an execution plan from the structured
travel request, resolved destination, and
relevant memory.

RULES:

1. Do NOT invent missing information.

2. A resolved destination is authoritative.

3. If a resolved destination is available,
   use that destination instead of the raw
   destination from the perception output.

4. Do NOT ask the user to clarify a destination
   that has already been resolved.

5. Do NOT create a clarification task for
   a resolved destination.

6. If important information other than the
   destination is missing or ambiguous,
   create a "clarify" task.

7. Never assume a year if the user did not
   provide one.

8. Consider the user's long-term preferences
   when they are relevant.

9. Consider relevant conversation history.

10. Do not treat unrelated memories as
    requirements.

11. Every task MUST have a unique short task_id.

12. depends_on MUST contain task IDs only.

13. A task can depend only on tasks that
    appear earlier in the task list.

14. Respect task dependencies.

15. Only create relevant tasks.

16. Do not execute the tasks.
    Only create the plan.

17. If clarification is required:
    - set needs_clarification = true
    - add the question to clarification_questions
    - create the clarification task first.

18. For transportation planning:
    - If transport_mode is "flight",
      create a transport task specifically
      for flight options.

    - If transport_mode is "train",
      create a transport task specifically
      for train options.

    - If transport_mode is "bus",
      create a transport task specifically
      for bus options.

    - If transport_mode is "any",
      create a transport task that considers
      flight, train, and bus options.

    - If transport_mode is "unknown",
      do not assume a transportation mode.
      Create a general transport task only when
      transportation planning is relevant to
      the user's request.

    - Never assume flight, train, or bus when
      transport_mode is "unknown".

19. For "check_weather" requests:
    - If the user asks for current weather,
      do NOT ask for travel dates.
    - If the user asks about weather during
      a future trip, dates may be required.

STRUCTURED USER REQUEST:

{perception.model_dump_json(indent=2)}

RESOLVED DESTINATION:

{resolved_destination}

MEMORY CONTEXT:

{memory_context}

Create the travel execution plan.
"""

        return structured_llm.invoke(
            prompt
        )