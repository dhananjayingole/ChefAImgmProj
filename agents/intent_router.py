"""agents/intent_router.py — Fixed all misrouting issues including diabetes recipe requests."""

import re
import json
from agents import state
from agents.base import BaseAgent
from agents.state import AgentState


class IntentRouter(BaseAgent):

    INTENTS = [
        "generate_recipe", "smart_recommendation", "modify_recipe",
        "view_inventory", "add_inventory", "remove_inventory", "remove_all_inventory",
        "health_advice", "greeting", "memory_recall",
        "meal_plan", "cooking_tips", "budget_analysis", "shopping_list",
        "daily_nutrition", "save_meal", "view_calendar",
        "rate_recipe", "eco_tips", "start_cooking_mode", "general",
    ]

    def __init__(self):
        super().__init__("🎯 Intent Agent")

    def run(self, state: AgentState, client=None, **kwargs) -> AgentState:
        query = state.get("user_query", "").strip()
        q = query.lower()

        intent = self._classify_rules(q, query)
        if intent:
            state["intent"] = intent
            state["intent_confidence"] = 0.95
            self.log(state, f"Intent → {intent} (rule)", "success")
            return state

        if client:
            intent = self._classify_llm(query, state, client)
        else:
            intent = "general"

        state["intent"] = intent
        state["intent_confidence"] = 0.80
        self.log(state, f"Intent → {intent} (LLM)", "success")
        return state

    def _classify_rules(self, q: str, raw: str) -> str:

        # ── Greeting ──────────────────────────────────────────────────────────
        if re.match(r"^(hi|hello|hey|good\s+(morning|evening|afternoon|night)|namaste|hii+|yo\b)\b", q):
            return "greeting"

        # ── Start cooking mode ────────────────────────────────────────────────
        if re.search(r"(start|begin|open|enter).*(cooking mode|cook mode|step.by.step|guided cook)", q):
            return "start_cooking_mode"
        if re.search(r"cooking mode.*(for|palak|dal|paneer|biryani|recipe)", q):
            return "start_cooking_mode"

        # ── Memory recall ─────────────────────────────────────────────────────
        if re.search(
            r"(what did i tell you|my (diet|preference|profile|goal|restriction|allerg)|"
            r"remind me|what do you know about me|what('s| is) my|do you remember|"
            r"what have i told|my saved|my stored)",
            q,
        ):
            return "memory_recall"

        # ── Profile setting (memory, not health) ──────────────────────────────
        if re.search(
            r"^(my (calorie|budget|cuisine|diet|goal|preference|cook time)|"
            r"i prefer|i like|i love|i want|set my|update my|change my)",
            q,
        ):
            return "memory_recall"

        # ── FIX: Diabetes recipe request → generate_recipe, not health_advice ──
        if re.search(
            r"(diabetes|diabetic).*(make me|generate|recipe|dinner|lunch|breakfast|cook|what can i eat)",
            q,
        ):
            return "generate_recipe"
        
        # ── Low carb / diabetic meal request ──────────────────────────────────
        if re.search(
            r"(low carb|low-carb|keto|diabetic friendly).*(dinner|meal|recipe|lunch|breakfast)",
            q,
        ):
            return "generate_recipe"

        # ── Daily nutrition ───────────────────────────────────────────────────
        if re.search(
            r"(daily nutrition|today'?s? (nutrition|calories?|intake|macros?)|"
            r"how (much|many).*(eaten|calories|protein|carbs)|"
            r"nutrition (dashboard|tracker|summary)|"
            r"(calories?|macros?).*(today|so far|eaten)|show.*nutrition|"
            r"progress today|what.*(eaten|consumed) today)",
            q,
        ):
            return "daily_nutrition"

        # ── Save meal ─────────────────────────────────────────────────────────
        if re.search(
            r"(save (this|last|that|the).*(recipe|meal|dinner|lunch|breakfast)|"
            r"log (this|that|the).*(meal|recipe|dinner)|"
            r"add.*(calendar|diary|log)|track this meal|save (as|for) (dinner|lunch|breakfast))",
            q,
        ):
            return "save_meal"

        # ── View calendar ─────────────────────────────────────────────────────
        if re.search(
            r"(meal calendar|show.*calendar|my (meal|eating|food) history|"
            r"what did i eat|show.*logged meals|meal log)",
            q,
        ):
            return "view_calendar"

        # ── Shopping list ─────────────────────────────────────────────────────
        if re.search(
            r"(shopping list|what (do i|should i) (buy|get|purchase)|"
            r"grocery list|what'?s? missing|what (to buy|to get)|"
            r"generate.*shopping|create.*list|items? (to buy|i need))",
            q,
        ):
            return "shopping_list"

        # ── Rate recipe ───────────────────────────────────────────────────────
        if re.search(
            r"(rate (this|that|the) recipe|give.*(\d+)\s*star|(\d+)\s*(star|out of 5)|"
            r"i (loved|liked|hated|disliked) (this|that|it)|"
            r"was (delicious|awful|good|bad|amazing|terrible)|"
            r"feedback (for|on) (this|that|the) recipe|"
            r"rate \d|^\d\s*stars?$)",
            q,
        ):
            return "rate_recipe"

        # ── Eco tips ──────────────────────────────────────────────────────────
        if re.search(
            r"(eco score|carbon footprint|co2|environmental impact|"
            r"sustainable (eating|food|meals?)|food waste|green (meal|recipe))",
            q,
        ):
            return "eco_tips"

        # ── Remove all ────────────────────────────────────────────────────────
        if re.search(r"(clear|empty|delete|remove).*(pantry|inventory|all)", q):
            return "remove_all_inventory"

        # ── Remove specific item ──────────────────────────────────────────────
        if re.search(
            r"(remove|delete|used up|finished|ran out of|no more|consumed|used all)\s+"
            r"(the\s+)?(paneer|spinach|tomato|rice|milk|onion|potato|egg|dal|lentil|"
            r"carrot|cauliflower|beans|curd|ghee|butter|oil|sugar|flour|basmati)",
            q,
        ):
            return "remove_inventory"

        # ── Add inventory with diet validation warning ────────────────────────
        if re.search(
            r"(i (bought|got|purchased|picked up)|just (bought|got)|"
            r"add.*(to.*)?(pantry|inventory|fridge))",
            q,
        ) and re.search(
            r"(\d+\s*(kg|g|ml|l|pieces?|cups?|bunch|liters?)|"
            r"paneer|spinach|tomato|rice|milk|onion|potato|egg|dal|lentil|"
            r"flour|sugar|oil|butter|ghee|yogurt|curd|beans|basmati|"
            r"carrot|cauliflower|capsicum)",
            q,
        ):
            # Check if adding non-veg for vegetarian
            profile = state.get("user_profile", {})
            diet = profile.get("diet_type", "").lower()
            if "vegetarian" in diet and re.search(r"(chicken|fish|shrimp|prawn|meat)", q):
                state["_diet_warning"] = True
            return "add_inventory"

        if re.match(r"^i have\s+\d", q):
            return "add_inventory"

        # ── View inventory ────────────────────────────────────────────────────
        if re.search(
            r"(show|view|list|check|what('s| is).*(in my|in the).*(pantry|fridge|inventory)|"
            r"what.*pantry|my (pantry|fridge|inventory)|pantry status)",
            q,
        ):
            return "view_inventory"

        if re.search(r"(what('s| is) expiring|expir(ing|ed)|use soon|going bad)", q):
            return "view_inventory"

        # ── Budget analysis ───────────────────────────────────────────────────
        if re.search(
            r"(cheapest|most affordable|best value|budget friendly|economical|"
            r"cheapest.*protein|protein.*cheap|best protein.*(budget|cheap|affordable)|"
            r"budget|how much.*cost|cost of|price of|afford|save money)",
            q,
        ):
            return "budget_analysis"

        # ── Health advice (now narrower) ──────────────────────────────────────
        if re.search(
            r"(diabetes|diabetic|hypertension|high blood pressure|cholesterol|celiac|"
            r"how many carbs|how much protein|recommended (intake|amount)|"
            r"should i eat|is.*good for (diabetic|health)|diet for (diabetes|weight)|"
            r"health (advice|tips?|recommendation)|nutrition (advice|tips?))",
            q,
        ):
            # Don't route if it's a recipe request
            if not re.search(r"(make me|recipe|generate|cook)", q):
                return "health_advice"

        # ── Smart recommendation ──────────────────────────────────────────────
        if re.search(
            r"(suggest|recommend|give me|what'?s? a good).*(breakfast|lunch|dinner|snack|meal|recipe)",
            q,
        ):
            return "smart_recommendation"

        # ── Meal plan ─────────────────────────────────────────────────────────
        if re.search(
            r"(plan my (meals?|week|day)|meal plan|weekly plan|"
            r"(\d+[\s-]day|week(ly)?|daily).*plan|plan.*(\d+\s*day|week))",
            q,
        ):
            return "meal_plan"

        # ── Cooking tips ──────────────────────────────────────────────────────
        if re.search(
            r"(how do i|how to (cook|make|prepare|fry|boil|bake|grill|roast)|tips? for|technique|"
            r"what temperature|how long.*cook|difference between|substitute for|"
            r"can i replace|what if i don't have)",
            q,
        ):
            return "cooking_tips"

        # ── Generate specific recipe ──────────────────────────────────────────
        if re.search(
            r"(make me|recipe for|how to make|i want to (make|cook)|"
            r"generate.*recipe|create.*recipe|give me.*recipe|show me.*recipe)",
            q,
        ):
            return "generate_recipe"

        DISHES = [
            "palak paneer", "dal tadka", "aloo gobi", "chole", "biryani",
            "dosa", "idli", "sambar", "rajma", "kadai", "paneer tikka",
            "pulao", "khichdi", "upma", "poha", "butter chicken",
            "pasta", "pizza", "soup", "sandwich", "stir fry",
            "halwa", "kheer", "raita",
        ]
        if any(dish in q for dish in DISHES):
            return "generate_recipe"

        return None

    def _classify_llm(self, query: str, state: AgentState, client) -> str:
        profile = state.get("user_profile", {})
        intents_str = ", ".join(self.INTENTS)

        prompt = f"""Classify this cooking assistant message into exactly one intent.

Available intents: {intents_str}

Critical rules:
- "start cooking mode for X" → start_cooking_mode (NOT generate_recipe)
- "suggest a high protein breakfast" → smart_recommendation (NOT health_advice)
- "cheapest protein source" → budget_analysis (NOT health_advice)
- "I have diabetes, make me a low carb dinner" → generate_recipe (NOT health_advice)
- "how many carbs for diabetic" → health_advice
- "my calorie goal is X" or "I prefer quick" → memory_recall
- "save last recipe as dinner" → save_meal
- "I bought X" → add_inventory

User message: "{query}"
User profile: diet={profile.get('diet_type','?')}, goal={profile.get('fitness_goal','?')}

Return ONLY the intent name, nothing else."""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=25,
            )
            intent = response.choices[0].message.content.strip().lower().replace("-", "_")
            if intent in self.INTENTS:
                return intent
        except Exception:
            pass
        return "general"


intelligent_router_agent = IntentRouter().run