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

        # ----------------------------------------------------
        # Default memory context
        # ----------------------------------------------------

        if memory_context is None:
            memory_context = {
                "conversation_history": [],
                "user_preferences": [],
                "resolved_destination": None,
            }

        # ----------------------------------------------------
        # Resolved destination
        # ----------------------------------------------------

        resolved_destination = (
            memory_context.get(
                "resolved_destination"
            )
        )

        # ----------------------------------------------------
        # Planner prompt
        # ----------------------------------------------------

        prompt = f"""
You are the planning layer of a professional
travel AI agent.

Create an execution plan from the structured
travel request, resolved destination, and
relevant memory.

IMPORTANT OUTPUT FORMAT:

Return the result as valid JSON.

The JSON must match the TravelPlan schema.

Do not return:
- markdown
- explanations
- plain text
- additional fields outside the schema

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

20. The TravelPlan must always contain
    a non-empty "goal".

21. Every task MUST use a task_type value
    supported by the TravelTask schema.

22. Allowed task_type values are ONLY:

    - "clarify"
    - "weather"
    - "transport"
    - "hotel"
    - "restaurant"
    - "itinerary"
    - "budget_check"
    - "other"

23. For hotel search or hotel availability
    requests, use:

    task_type = "hotel"

    NEVER use:
    - "hotel_search"
    - "search_hotel"
    - "hotel_booking"

24. For flight, train, bus, or general
    transportation search requests, use:

    task_type = "transport"

    NEVER create task types such as:
    - "flight_search"
    - "train_search"
    - "bus_search"

25. For weather requests, use:

    task_type = "weather"

26. For restaurant requests, use:

    task_type = "restaurant"

27. For itinerary planning, use:

    task_type = "itinerary"

28. For budget-related validation, use:

    task_type = "budget_check"

29. For clarification, use:

    task_type = "clarify"

30. The output must contain the exact field
    name "task_type" for every task.

    Do NOT use "type".

31. The output must contain the "goal" field
    at the top level of the TravelPlan.

32. Do not create additional task_type values
    outside the allowed list.

STRUCTURED USER REQUEST:

{perception.model_dump_json(indent=2)}

RESOLVED DESTINATION:

{resolved_destination}

MEMORY CONTEXT:

{memory_context}

OUTPUT CONTRACT:

Return a JSON object matching the TravelPlan schema.

The top-level object MUST contain:

{{
    "goal": "...",
    "needs_clarification": false,
    "clarification_questions": [],
    "tasks": []
}}

Every task MUST contain:

{{
    "task_id": "...",
    "task_type": "...",
    "description": "...",
    "required": true,
    "depends_on": []
}}

IMPORTANT:

- Use "task_type", never "type".
- Use only the allowed task_type values.
- For hotel work, use "hotel".
- For transport work, use "transport".
- For weather work, use "weather".
- For restaurant work, use "restaurant".
- For itinerary work, use "itinerary".
- For clarification, use "clarify".
- Always provide a non-empty "goal".
- Return JSON only.
- Do not return markdown.
- Do not return explanations outside the JSON object.

Create the travel execution plan.
"""

        # ----------------------------------------------------
        # Generate structured TravelPlan through the
        # centralized LLM router.
        #
        # The router handles provider fallback:
        # Groq → OpenRouter → Gemini → OpenAI
        # ----------------------------------------------------

        return self.llm_router.invoke_structured(
            prompt=prompt,
            schema=TravelPlan,
        )