"""
agents/streaming_pipeline.py — Full multi-user support.
Every pipeline run reads state["user_id"] and routes to that user's private databases.
"""

import time
import re
from typing import Generator
from agents.state import AgentState
from agents.pantry_agent import detect_pantry_intent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe(fn, state, *args, **kwargs):
    """Call fn safely; return (state, error_str|None)."""
    try:
        result = fn(*args, **kwargs)
        return (result if result is not None else state), None
    except Exception as e:
        return state, str(e)


def _stream(text: str, delay: float = 0.004) -> Generator:
    for ch in str(text):
        yield {"type": "token", "text": ch}
        time.sleep(delay)


def _phase(agent: str, status: str, **extra):
    return {"type": "phase", "agent": agent, "status": status, **extra}


def _guard_intent(state: AgentState) -> AgentState:
    """Override 'general' intent when pantry patterns are detected."""
    if state.get("intent", "general") != "general":
        return state
    detected = detect_pantry_intent(state.get("user_query", ""))
    if detected:
        state["intent"] = detected
    return state


def _resolve_user_services(state: AgentState, db, profile_db, feedback_db):
    """
    If state carries a user_id, always use that user's private databases
    instead of whatever was passed as positional args.
    This is the central isolation gate — all code paths funnel through here.
    """
    user_id = state.get("user_id")
    if user_id:
        try:
            from services.user_services import get_user_services
            svc        = get_user_services(user_id)
            db         = svc["db"]
            profile_db = svc["profile_db"]
            feedback_db = svc["feedback_db"]
        except Exception:
            pass   # Fallback to whatever was passed in — better than crashing
    return db, profile_db, feedback_db


# ── Main streaming pipeline ───────────────────────────────────────────────────

def run_streaming_pipeline(
    state: AgentState,
    client,
    db,
    recipe_kb,
    profile_db=None,
    feedback_db=None,
) -> Generator:
    """
    Multi-user safe pipeline.
    If state["user_id"] is set, every DB operation is routed to that user's
    private SQLite files regardless of what db/profile_db/feedback_db were passed.
    """

    # ── ISOLATION GATE: override DBs from user_id in state ───────────────
    db, profile_db, feedback_db = _resolve_user_services(
        state, db, profile_db, feedback_db
    )

    # ── Phase 1: Memory ───────────────────────────────────────────────────
    yield _phase("🧠 Memory Agent", "running")
    t0 = time.time()
    try:
        from agents.memory_agent import MemoryAgent
        ma    = MemoryAgent()
        state, err = _safe(ma.run, state, state, profile_db=profile_db, client=client)
    except Exception as e:
        err = str(e)
    yield _phase("🧠 Memory Agent", "done" if not err else "error",
                 time=round(time.time() - t0, 2))

    # ── Phase 2: Intent ───────────────────────────────────────────────────
    yield _phase("🎯 Intent Agent", "running")
    t0 = time.time()
    try:
        from agents.intent_router import intelligent_router_agent
        state, _ = _safe(intelligent_router_agent, state, state, client=client)
    except Exception:
        pass
    state  = _guard_intent(state)
    intent = state.get("intent", "general")
    yield _phase("🎯 Intent Agent", "done", time=round(time.time() - t0, 2), intent=intent)

    # ════════════════════════════════════════════════════════════════════════
    # GREETING
    # ════════════════════════════════════════════════════════════════════════
    if intent == "greeting":
        profile   = state.get("user_profile", {})
        diet_hint = f" I know you're {profile['diet_type']}." if profile.get("diet_type") else ""
        msg = (
            f"👋 Hey there! I'm **NutriBot**, your smart meal assistant.{diet_hint}\n\n"
            "Here's what I can do:\n"
            "• 📦 **Track pantry** — tell me what you bought\n"
            "• 🍳 **Generate recipes** — personalised to your diet & health\n"
            "• 📅 **Plan weekly meals** — balanced & within budget\n"
            "• 📊 **Track nutrition** — daily calories, protein, carbs\n"
            "• 💰 **Budget tips** — real ₹ prices\n"
            "• 🛒 **Shopping lists** — only what you need\n"
            "• 🌱 **Eco scores** — reduce food waste\n\n"
            "What would you like to do today?"
        )
        state["assistant_message"] = msg
        yield from _stream(msg)
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # MEMORY RECALL
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "memory_recall":
        yield _phase("🧠 Memory Agent", "running")
        t0 = time.time()
        try:
            state, err = _safe(ma.recall, state, state, client)
        except Exception as e:
            err = str(e)
        yield _phase("🧠 Memory Agent", "done" if not err else "error",
                     time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", "No profile found."))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # PANTRY: ADD
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "add_inventory":
        yield _phase("📦 Pantry Agent", "running")
        t0 = time.time()
        from agents.pantry_agent import PantryAgent
        state = PantryAgent()._add_items(state, client, db)
        yield _phase("📦 Pantry Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", "❌ Could not add items."))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # PANTRY: VIEW
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "view_inventory":
        yield _phase("📦 Pantry Agent", "running")
        t0 = time.time()
        from agents.pantry_agent import PantryAgent
        state = PantryAgent()._view_pantry(state, db)
        yield _phase("📦 Pantry Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", "Pantry is empty."))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # PANTRY: REMOVE / CLEAR
    # ════════════════════════════════════════════════════════════════════════
    elif intent in ("remove_inventory", "remove_all_inventory"):
        yield _phase("📦 Pantry Agent", "running")
        t0 = time.time()
        from agents.pantry_agent import PantryAgent
        pa = PantryAgent()
        if intent == "remove_all_inventory":
            state = pa._clear_pantry(state, db)
        else:
            state = pa._remove_items(state, client, db)
        yield _phase("📦 Pantry Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", "Done."))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # RECIPE / RECOMMENDATION / MODIFY
    # ════════════════════════════════════════════════════════════════════════
    elif intent in ("generate_recipe", "smart_recommendation", "modify_recipe"):
        yield from _run_recipe_pipeline(state, client, db, recipe_kb)
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # MEAL PLAN
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "meal_plan":
        yield _phase("📅 Meal Planner", "running")
        t0 = time.time()
        try:
            from agents.planner_agent import meal_plan_agent
            state = meal_plan_agent(state, client=client, db=db)
        except Exception as e:
            state["assistant_message"] = f"Could not generate meal plan: {e}"
        yield _phase("📅 Meal Planner", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # SHOPPING LIST
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "shopping_list":
        yield _phase("🛒 Shopping Agent", "running")
        t0 = time.time()
        try:
            from agents.shopping_agent import shopping_agent
            state = shopping_agent(state, db=db, client=client)
        except Exception as e:
            state["assistant_message"] = f"Could not generate shopping list: {e}"
        yield _phase("🛒 Shopping Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # DAILY NUTRITION
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "daily_nutrition":
        yield _phase("📊 Nutrition Agent", "running")
        t0 = time.time()
        try:
            from agents.nutrition_tracker import get_daily_nutrition_summary
            state = get_daily_nutrition_summary(state, db, client)
        except Exception as e:
            state["assistant_message"] = f"Could not load nutrition data: {e}"
        yield _phase("📊 Nutrition Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # SAVE MEAL
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "save_meal":
        yield _phase("📅 Meal Planner", "running")
        t0 = time.time()
        try:
            from agents.nutrition_tracker import save_meal_to_calendar
            if not state.get("generated_recipe"):
                last = _find_last_recipe(state)
                if last:
                    state["generated_recipe"] = last
            q_lower   = state.get("user_query", "").lower()
            meal_type = "dinner"
            for mt in ["breakfast", "lunch", "snack"]:
                if mt in q_lower:
                    meal_type = mt
                    break
            state = save_meal_to_calendar(state, db, meal_type)
        except Exception as e:
            state["assistant_message"] = f"Could not save meal: {e}"
        yield _phase("📅 Meal Planner", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # HEALTH ADVICE
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "health_advice":
        yield _phase("🏥 Health Agent", "running")
        t0 = time.time()
        try:
            from agents.health_agent import health_agent
            state = health_agent(state, client=client)
        except Exception as e:
            state["assistant_message"] = _health_fallback(state, client)
        yield _phase("🏥 Health Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # ECO TIPS
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "eco_tips":
        yield _phase("🌱 Eco Agent", "running")
        t0 = time.time()
        msg = _eco_response(state, db)
        state["assistant_message"] = msg
        yield _phase("🌱 Eco Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(msg)
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # BUDGET ANALYSIS
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "budget_analysis":
        yield _phase("💰 Budget Agent", "running")
        t0 = time.time()
        msg = _build_budget_response(state, client)
        state["assistant_message"] = msg
        yield _phase("💰 Budget Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(msg)
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # COOKING TIPS
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "cooking_tips":
        yield _phase("🍳 Recipe Agent", "running")
        t0 = time.time()
        try:
            profile = state.get("user_profile", {})
            query   = state.get("user_query", "")
            prompt  = (
                f'You are an expert Indian chef. Answer precisely:\n\n"{query}"\n\n'
                f'User: {profile.get("diet_type","vegetarian")}, '
                f'{profile.get("skill_level","intermediate")} cook.\n\n'
                "Give: direct answer, exact times/temps, common mistakes, one pro tip.\n"
                "Under 200 words. Use bullet points."
            )
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.4, max_tokens=400,
            )
            msg = resp.choices[0].message.content.strip()
        except Exception as e:
            msg = f"Cooking tips unavailable: {e}"
        state["assistant_message"] = msg
        yield _phase("🍳 Recipe Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(msg)
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # RATE RECIPE
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "rate_recipe":
        yield _phase("⭐ Taste Agent", "running")
        t0 = time.time()
        state = _handle_rating(state, feedback_db)
        yield _phase("⭐ Taste Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # VIEW CALENDAR
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "view_calendar":
        yield _phase("📅 Meal Planner", "running")
        t0 = time.time()
        try:
            from datetime import date
            from collections import defaultdict
            meals = db.get_meal_plans(days=7) if db else []
            if meals:
                by_date = defaultdict(list)
                for m in meals:
                    by_date[m.get("plan_date", "?")].append(m)
                lines = ["## 📅 Meal Calendar — Last 7 Days\n"]
                for d in sorted(by_date.keys(), reverse=True):
                    label     = "**Today**" if d == date.today().isoformat() else f"**{d}**"
                    total_cal = 0
                    lines.append(label)
                    for m in by_date[d]:
                        cal = m.get("calories", 0)
                        total_cal += cal
                        lines.append(f"  • {m.get('meal_type','').title()}: {m.get('recipe_name','')} ({cal} kcal)")
                    lines.append(f"  *Total: {total_cal} kcal*\n")
                msg = "\n".join(lines)
            else:
                msg = (
                    "📅 **No meals logged yet.**\n\n"
                    "After generating a recipe, say *'save this as dinner'* to start tracking."
                )
            state["assistant_message"] = msg
        except Exception as e:
            state["assistant_message"] = f"Could not load calendar: {e}"
        yield _phase("📅 Meal Planner", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # START COOKING MODE
    # ════════════════════════════════════════════════════════════════════════
    elif intent == "start_cooking_mode":
        yield _phase("🍳 Recipe Agent", "running")
        t0 = time.time()
        recipe = state.get("generated_recipe", "") or _find_last_recipe(state)
        if recipe:
            state["assistant_message"] = (
                "🍳 **Cooking Mode Ready!**\n\n"
                "Click **'🍳 Start Cooking Mode'** button to begin step-by-step guidance.\n\n"
                "I'll walk you through each step with timers."
            )
        else:
            state["assistant_message"] = "❌ No recipe found. Please generate a recipe first."
        yield _phase("🍳 Recipe Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(state.get("assistant_message", ""))
        yield {"type": "complete", "state": state}
        return

    # ════════════════════════════════════════════════════════════════════════
    # GENERAL FALLBACK
    # ════════════════════════════════════════════════════════════════════════
    else:
        yield _phase("🧠 Memory Agent", "running")
        t0 = time.time()
        msg = _general_response(state, client)
        state["assistant_message"] = msg
        yield _phase("🧠 Memory Agent", "done", time=round(time.time() - t0, 2))
        yield from _stream(msg)
        yield {"type": "complete", "state": state}
        return


# ── Recipe sub-pipeline ───────────────────────────────────────────────────────

def _run_recipe_pipeline(state, client, db, recipe_kb) -> Generator:
    from agents.budget_agent import budget_agent
    from agents.nutrition_agent import _calculate_nutrition

    # Pantry context
    yield _phase("🥕 Pantry Agent", "running")
    t0        = time.time()
    groceries = db.get_all_groceries() if db else []
    expiring  = db.get_expiring_soon(days=3) if db else []
    state["available_ingredients"] = [g["item_name"] for g in groceries]
    if expiring:
        exp_names = [e["item_name"] for e in expiring[:3]]
        state["user_query"] = (
            state.get("user_query", "")
            + f" (prioritise using: {', '.join(exp_names)} which are expiring soon)"
        )
    yield _phase("🥕 Pantry Agent", "done", time=round(time.time() - t0, 2))

    # Recipe generation
    yield _phase("🍳 Recipe Agent", "running")
    t0 = time.time()
    try:
        from agents.receipe_agent import RecipeAgent
        ra    = RecipeAgent()
        state, err = _safe(ra.run, state, state, client=client)
    except Exception as e:
        state["generated_recipe"] = f"Recipe generation failed: {e}"
    recipe = state.get("generated_recipe", "")
    yield from _stream(recipe)
    yield _phase("🍳 Recipe Agent", "done", time=round(time.time() - t0, 2))

    _extract_ingredients(state, recipe)

    # Nutrition
    yield _phase("📊 Nutrition Agent", "running")
    t0 = time.time()
    try:
        ings     = state.get("recipe_ingredients_structured", [])
        servings = state.get("servings", 2)
        if ings:
            state = _calculate_nutrition(state, ings, servings, client)
    except Exception:
        pass
    yield _phase("📊 Nutrition Agent", "done", time=round(time.time() - t0, 2))
    if state.get("nutrition_data"):
        yield {"type": "section", "title": "📊 Nutrition", "content": state["nutrition_data"]}

    # Budget
    yield _phase("💰 Budget Agent", "running")
    t0 = time.time()
    try:
        state = budget_agent(state)
    except Exception:
        pass
    yield _phase("💰 Budget Agent", "done", time=round(time.time() - t0, 2))
    if state.get("budget_analysis"):
        yield {"type": "section", "title": "💰 Budget", "content": state["budget_analysis"]}

    # Eco
    yield _phase("🌱 Eco Agent", "running")
    t0 = time.time()
    try:
        from agents.eco_agent import eco_agent
        state = eco_agent(state, db=db)
    except Exception:
        pass
    yield _phase("🌱 Eco Agent", "done", time=round(time.time() - t0, 2))
    if state.get("eco_score"):
        yield {"type": "section", "title": "🌱 Eco", "content": state["eco_score"]}

    # Health
    yield _phase("🏥 Health Agent", "running")
    t0 = time.time()
    try:
        from agents.health_agent import health_agent
        state = health_agent(state, client=client)
    except Exception:
        pass
    yield _phase("🏥 Health Agent", "done", time=round(time.time() - t0, 2))
    rec = state.get("health_recommendations", "")
    if rec and "✅" not in rec and len(rec) > 10:
        yield {"type": "section", "title": "🏥 Health", "content": rec}


# ── Ingredient extraction ─────────────────────────────────────────────────────

def _extract_ingredients(state: AgentState, recipe_text: str):
    if not recipe_text:
        return
    pattern = re.compile(
        r"[-•]\s*([0-9½¼¾]+(?:[./][0-9]+)?)\s*"
        r"(kg|g|grams?|ml|l|liters?|cups?|tbsp|tsp|pieces?|bunch|cloves?|pinch|medium|large|small)?\s*"
        r"([a-zA-Z][a-zA-Z\s\-]+?)(?:\s*[,\(~\n]|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    ing_section = re.search(
        r"###\s*📋\s*Ingredients\s*\n(.*?)(?=\n###|\n##|$)",
        recipe_text, re.DOTALL | re.IGNORECASE,
    )
    search_text = ing_section.group(1) if ing_section else recipe_text
    ingredients = []
    for m in pattern.finditer(search_text):
        qs   = m.group(1).replace("½","0.5").replace("¼","0.25").replace("¾","0.75")
        unit = m.group(2) or "grams"
        name = m.group(3).strip().rstrip("(~, ")
        try:
            qty = float(qs)
        except ValueError:
            qty = 1.0
        if 2 < len(name) < 40:
            ingredients.append({"name": name.lower(), "quantity": qty, "unit": unit.lower()})
    if ingredients:
        state["recipe_ingredients_structured"] = ingredients


# ── Rating handler ────────────────────────────────────────────────────────────

def _handle_rating(state: AgentState, feedback_db) -> AgentState:
    query = state.get("user_query", "")
    star_match = re.search(r"(\d)\s*(?:star|/5|out of)", query.lower())
    if star_match:
        rating = int(star_match.group(1))
    elif any(w in query.lower() for w in ["loved","amazing","delicious","excellent"]):
        rating = 5
    elif any(w in query.lower() for w in ["good","liked","nice","great"]):
        rating = 4
    elif any(w in query.lower() for w in ["okay","average","alright"]):
        rating = 3
    elif any(w in query.lower() for w in ["bad","disliked","not great"]):
        rating = 2
    else:
        rating = 4

    last_recipe  = _find_last_recipe(state)
    recipe_name  = "Previous Recipe"
    if last_recipe:
        nm = re.search(r"##\s*🍽️\s*(.+)", last_recipe)
        if nm:
            recipe_name = nm.group(1).strip()

    if feedback_db:
        try:
            profile     = state.get("user_profile", {})
            nutrition   = state.get("total_nutrition", {})
            ingredients = [i.get("name","") for i in state.get("recipe_ingredients_structured",[])]
            cp          = profile.get("cuisine_preferences", ["Indian"])
            cuisine     = cp[0] if isinstance(cp, list) and cp else "Indian"
            feedback_db.save_rating(
                recipe_name    = recipe_name,
                rating         = rating,
                recipe_content = last_recipe[:500],
                cuisine        = cuisine,
                diet_type      = profile.get("diet_type",""),
                calories       = nutrition.get("calories", 0),
                ingredients    = ingredients,
                session_id     = state.get("session_id",""),
            )
        except Exception:
            pass

    stars     = "⭐" * rating + "☆" * (5 - rating)
    reactions = {
        5: "Wonderful! I'll suggest similar recipes more often.",
        4: "Great feedback! I'll remember what you enjoyed.",
        3: "Thanks — I'll try to improve next time.",
        2: "Sorry it wasn't great. I'll suggest something different.",
        1: "I'll avoid this style entirely.",
    }
    state["assistant_message"] = (
        f"## {stars} Rating Saved!\n\n"
        f"**{recipe_name}** — {rating}/5 stars\n\n"
        f"{reactions.get(rating,'Thanks!')}\n\n"
        f"*Your taste profile is now smarter — better recommendations coming!*"
    )
    return state


def _find_last_recipe(state: AgentState) -> str:
    history = state.get("conversation_history", [])
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if "## 🍽️" in content and "### 📋 Ingredients" in content:
                return content
    return ""


# ── Budget response ───────────────────────────────────────────────────────────

def _build_budget_response(state: AgentState, client) -> str:
    profile = state.get("user_profile", {})
    try:
        from services.price_service import PriceService
        from agents.user_profile import _currency
        ps           = PriceService()
        cur          = _currency(profile)
        diet         = profile.get("diet_type", "vegetarian")
        cheapest     = ps.get_cheapest_protein(diet)
        bp           = profile.get("budget_preference", {})
        budget_amt   = bp.get("amount", 500) if isinstance(bp, dict) else 500
        protein_name  = cheapest.get("name",            "lentil (dal)")
        protein_price = cheapest.get("price_per_kg",    80)
        protein_g     = cheapest.get("protein_per_100g",24)
        return (
            f"## 💰 Budget Analysis\n\n"
            f"**Your weekly budget:** {cur}{budget_amt}\n\n"
            f"**Best value protein:** **{protein_name.title()}** — "
            f"{cur}{protein_price}/kg | {protein_g}g protein/100g\n\n"
            f"**₹500/week staples:**\n"
            f"| Item | Cost |\n|------|------|\n"
            f"| 1kg Dal | ₹80-120 |\n| 2kg Rice | ₹120 |\n"
            f"| 1kg Onion | ₹40 |\n| 500g Tomato | ₹30 |\n"
            f"| 500g Paneer | ₹140 |\n| 1kg Spinach | ₹40 |\n"
            f"| Spices | ₹30 |\n| **Total** | **~₹480** ✅ |"
        )
    except Exception:
        return (
            "## 💰 Budget Tips (₹500/week)\n\n"
            "• Soy chunks: ₹120/kg — 52g protein/100g ⭐\n"
            "• Dal: ₹80-120/kg — 24g protein/100g\n"
            "• Chickpeas: ₹80/kg — 19g protein/100g\n"
            "• Paneer: ₹280/kg — use sparingly"
        )


# ── Eco response ──────────────────────────────────────────────────────────────

def _eco_response(state: AgentState, db) -> str:
    eco      = state.get("eco_score", {})
    expiring = db.get_expiring_soon(days=3) if db else []
    lines    = ["## 🌱 Eco Score & Carbon Tips\n"]
    if eco:
        score = eco.get("score", 0)
        grade = eco.get("grade", "?")
        co2   = eco.get("co2_kg", 0)
        saved = eco.get("co2_saved_kg", 0)
        tips  = eco.get("all_tips", [])
        color = {"A+":"🟢","A":"🟢","B":"🟡","C":"🟡","D":"🔴"}.get(grade,"🟡")
        lines += [
            f"**Last recipe:** {color} {score:.0f}/100 — Grade **{grade}**",
            f"• CO₂ used: {co2:.2f} kg  |  CO₂ saved: {saved:.2f} kg",
        ]
        if tips:
            lines.append("\n**Why:**")
            lines.extend(f"• {t}" for t in tips)
    else:
        lines.append("*Generate a recipe to see your eco score!*\n")
    if expiring:
        lines += ["", "**⚠️ Use before expiry (+10 eco pts each):**"]
        for e in expiring[:5]:
            lines.append(f"• 🔴 {e['item_name'].title()}")
    lines += [
        "",
        "**🌍 General eco tips:**",
        "• Vegetarian meals → 60% less CO₂ than beef",
        "• Seasonal local veg → 70% lower carbon footprint",
        "• Lentils/dal → most sustainable protein available",
    ]
    return "\n".join(lines)


# ── General fallback ──────────────────────────────────────────────────────────

def _general_response(state: AgentState, client) -> str:
    try:
        profile  = state.get("user_profile", {})
        history  = state.get("conversation_history", [])
        query    = state.get("user_query", "")
        hist_txt = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-6:]
        ) if history else ""
        from agents.user_profile import get_profile_context_string
        prompt = (
            f"You are NutriBot, a smart meal assistant specialising in Indian nutrition.\n\n"
            f"{get_profile_context_string(profile)}\n\n"
            + (f"CONVERSATION:\n{hist_txt}\n\n" if hist_txt else "")
            + f"USER: {query}\n\nBe helpful, warm, specific. Under 200 words."
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.5, max_tokens=350,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return (
            "I'm here to help! Try:\n"
            "• 📦 'I bought 500g paneer'\n"
            "• 🍳 'Make me palak paneer'\n"
            "• 📅 'Plan my meals for 3 days'\n"
            "• 📊 'Show my daily nutrition'"
        )


def _health_fallback(state: AgentState, client) -> str:
    try:
        profile = state.get("user_profile", {})
        query   = state.get("user_query", "")
        conds   = profile.get("health_conditions", [])
        prompt  = (
            f'You are a certified nutritionist. Answer:\n\n"{query}"\n\n'
            f'Patient: {profile.get("diet_type","vegetarian")}, conditions: {conds}\n\n'
            "Evidence-based, practical, under 250 words."
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3, max_tokens=450,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "Health advice is temporarily unavailable."