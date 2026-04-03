"""agents/memory_agent.py — Fixed budget amount display."""

import re
import json
from datetime import datetime
from agents.base import BaseAgent
from agents.state import AgentState
from agents.user_profile import get_profile_context_string

class MemoryAgent(BaseAgent):
    """Manages user profile and conversation context."""

    def __init__(self):
        super().__init__("🧠 Memory Agent")

    def run(self, state: AgentState, profile_db=None, client=None, **kwargs) -> AgentState:
        # Keep your existing run implementation
        if profile_db:
            profile = self._extract_and_update_profile(
                state.get("user_query", ""),
                state.get("conversation_history", []),
                profile_db,
                client,
            )
            state["user_profile"] = profile
        else:
            state.setdefault("user_profile", {})

        profile = state.get("user_profile", {})
        if profile:
            if profile.get("diet_type") and not state.get("dietary_restrictions"):
                state["dietary_restrictions"] = [profile["diet_type"]]
            if profile.get("cuisine_preferences") and not state.get("cuisine_preference"):
                prefs = profile["cuisine_preferences"]
                state["cuisine_preference"] = prefs[0] if isinstance(prefs, list) else prefs
            if profile.get("calorie_goal") and not state.get("calorie_limit"):
                state["calorie_limit"] = profile["calorie_goal"]

            # FIXED: Get budget amount correctly
            bp = profile.get("budget_preference", {})
            if isinstance(bp, dict) and bp.get("amount") and not state.get("budget_limit"):
                state["budget_limit"] = float(bp["amount"])

            if profile.get("servings_preference") and not state.get("servings"):
                state["servings"] = int(profile["servings_preference"])

        return state

    def _extract_and_update_profile(self, message: str, history: list, profile_db, client) -> dict:
        from agents.user_profile import profile_extraction_agent
        return profile_extraction_agent(message, history, profile_db, client)

    def recall(self, state: AgentState, client) -> AgentState:
        """Answer questions about stored preferences without hallucination."""
        profile = state.get("user_profile", {})
        
        # Build explicit list of known facts
        known_facts = []
        
        if profile.get("name"):
            known_facts.append(f"• Your name: **{profile['name']}**")
        
        if profile.get("diet_type"):
            known_facts.append(f"• Diet: **{profile['diet_type']}**")
        
        if profile.get("fitness_goal"):
            known_facts.append(f"• Goal: **{profile['fitness_goal'].replace('_', ' ').title()}**")
        
        if profile.get("cuisine_preferences"):
            cuisines = profile["cuisine_preferences"]
            if isinstance(cuisines, list):
                known_facts.append(f"• Cuisine preferences: **{', '.join(cuisines)}**")
            else:
                known_facts.append(f"• Cuisine preferences: **{cuisines}**")
        
        if profile.get("health_conditions"):
            conditions = profile["health_conditions"]
            if isinstance(conditions, list):
                known_facts.append(f"• Health conditions: **{', '.join(conditions)}**")
            else:
                known_facts.append(f"• Health conditions: **{conditions}**")
        
        if profile.get("allergies"):
            allergies = profile["allergies"]
            if isinstance(allergies, list):
                known_facts.append(f"• Allergies: **{', '.join(allergies)}**")
            else:
                known_facts.append(f"• Allergies: **{allergies}**")
        
        # FIXED: Proper budget display with amount
        if profile.get("budget_preference"):
            bp = profile["budget_preference"]
            if isinstance(bp, dict):
                currency = bp.get("currency", "₹")
                amount = bp.get("amount", "")
                if amount:
                    known_facts.append(f"• Budget: **{currency}{amount}/week**")
                else:
                    known_facts.append(f"• Budget: **{currency}500/week** (default)")
            elif isinstance(bp, (int, float)):
                known_facts.append(f"• Budget: **₹{bp}/week**")
        
        if profile.get("calorie_goal"):
            known_facts.append(f"• Calorie goal: **{profile['calorie_goal']} kcal/meal**")
        
        if profile.get("cooking_time_preference"):
            known_facts.append(f"• Cooking time preference: **{profile['cooking_time_preference']}**")
        
        if known_facts:
            state["assistant_message"] = (
                "Here's what I know about you:\n\n" + 
                "\n".join(known_facts) +
                "\n\nIs there anything else you'd like to add or update?"
            )
        else:
            state["assistant_message"] = (
                "I haven't learned anything about you yet! "
                "Tell me about your diet, goals, and preferences. "
                "For example: *'I'm vegetarian, trying to lose weight, and love Indian food'*"
            )
        
        return state