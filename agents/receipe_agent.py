"""agents/recipe_agent.py — Fixed: allergy enforcement, cooking time respect, no eggs for vegetarians, and diet validation."""

import re
import json
from agents.base import BaseAgent
from agents.state import AgentState
from agents.user_profile import get_profile_context_string, get_diet_constraints_string, _currency

# Hard forbidden lists per diet
FORBIDDEN = {
    "vegetarian": ["chicken", "beef", "pork", "fish", "mutton", "lamb", "prawn",
                   "shrimp", "bacon", "meat", "salmon", "tuna", "seafood"],
    "vegan": ["chicken", "beef", "pork", "fish", "mutton", "lamb", "prawn",
              "shrimp", "bacon", "meat", "salmon", "milk", "cheese", "egg",
              "butter", "ghee", "honey", "cream", "paneer", "yogurt", "curd"],
    "keto": ["rice", "pasta", "bread", "sugar", "flour", "potato", "corn", "oats"],
}

# In Indian vegetarian context eggs are excluded by most vegetarians
INDIAN_VEG_EXCLUDE = ["egg", "eggs", "omelette", "omelet"]


class RecipeAgent(BaseAgent):

    def __init__(self):
        super().__init__("🍳 Recipe Agent")

    def run(self, state: AgentState, client=None, **kwargs) -> AgentState:
        intent = state.get("intent", "generate_recipe")
        
        # First, check if requested dish violates diet
        query = state.get("user_query", "").lower()
        profile = state.get("user_profile", {})
        diet_type = profile.get("diet_type", "").lower()
        
        # Check if user is asking for non-veg dish
        if "vegetarian" in diet_type:
            non_veg_dishes = ["chicken", "fish", "shrimp", "prawn", "meat", "beef", "pork", "lamb"]
            for nv in non_veg_dishes:
                if nv in query:
                    state["assistant_message"] = (
                        f"⚠️ I notice you're asking about **{nv}**, but your profile says you're **vegetarian**.\n\n"
                        f"I'll generate a delicious **vegetarian alternative** instead. Would you like me to proceed with a "
                        f"{'paneer' if 'chicken' in nv else 'tofu' if 'fish' in nv else 'vegetable'} version?"
                    )
                    # Modify query to be vegetarian
                    state["user_query"] = query.replace(nv, "paneer" if "chicken" in nv else "tofu")
        
        for attempt in range(3):
            try:
                recipe, ingredients = self._generate(state, client, intent, attempt)
                profile = state.get("user_profile", {})
                diet_type = profile.get("diet_type", "")
                allergies = profile.get("allergies", [])
                if isinstance(allergies, str):
                    allergies = [allergies]

                violations = self._check_violations(recipe, diet_type, allergies)
                
                # Also check ingredients for violations
                ingredient_violations = self._check_ingredient_violations(ingredients, diet_type, allergies)
                all_violations = violations + ingredient_violations

                if not all_violations or attempt == 2:
                    state["generated_recipe"] = recipe
                    state["recipe_ingredients_structured"] = ingredients
                    state["assistant_message"] = recipe
                    # Store nutrition for saving
                    nutrition = self._extract_nutrition_from_recipe(recipe)
                    if nutrition:
                        state["last_generated_nutrition"] = nutrition
                        state["total_nutrition"] = nutrition
                    if all_violations:
                        self.log(state, f"⚠️ Residual violations: {all_violations}", "warning")
                    break
                else:
                    self.log(state, f"Attempt {attempt+1}: violations {all_violations}, retrying", "warning")
                    state["_last_violations"] = all_violations
            except Exception as e:
                if attempt == 2:
                    state["generated_recipe"] = f"❌ Could not generate recipe: {e}"
                    state["assistant_message"] = state["generated_recipe"]
                    self.log(state, f"Error: {e}", "error")
        return state

    def _generate(self, state: AgentState, client, intent: str, attempt: int) -> tuple:
        prompt = self._build_prompt(state, intent, attempt)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.65,
            max_tokens=2200,
        )
        recipe_text = response.choices[0].message.content.strip()
        
        # Extract structured ingredients
        ingredients = self._extract_ingredients(recipe_text)
        
        return recipe_text, ingredients

    def _build_prompt(self, state: AgentState, intent: str, attempt: int) -> str:
        profile = state.get("user_profile", {})
        cur = _currency(profile)
        diet_type = profile.get("diet_type", "")
        diet_constraints = get_diet_constraints_string(profile)
        allergies = profile.get("allergies", [])
        if isinstance(allergies, str):
            allergies = [allergies]
        health_conditions = profile.get("health_conditions", [])
        if isinstance(health_conditions, str):
            health_conditions = [health_conditions]

        # Build allergy block
        allergy_block = ""
        if allergies:
            allergy_block = f"\n  ⚠️ ALLERGIES — NEVER USE: {', '.join(allergies)}"
            # Expand nut allergy
            if any("nut" in a.lower() for a in allergies):
                allergy_block += (
                    "\n  ⚠️ NUT ALLERGY EXPANSION: also exclude almonds, cashews, "
                    "pistachios, walnuts, peanuts, almond butter, nut oils, marzipan"
                )

        # Health condition constraints
        health_block = ""
        conds = [h.lower() for h in health_conditions]
        if "diabetes" in conds:
            health_block += "\n  ⚠️ DIABETES: keep carbs ≤45g/serving, low GI foods, no refined sugar or white rice"
        if "hypertension" in conds:
            health_block += "\n  ⚠️ HYPERTENSION: sodium <600mg/serving, no added salt beyond recipe minimum"

        # Indian vegetarian egg exclusion
        egg_note = ""
        if diet_type and "vegetarian" in diet_type.lower() and "non" not in diet_type.lower():
            egg_note = "\n  ⚠️ INDIAN VEGETARIAN: do NOT use eggs, omelette, or egg-based dishes"

        # Retry feedback
        retry_block = ""
        if attempt > 0 and state.get("_last_violations"):
            retry_block = (
                f"\n⚠️ PREVIOUS ATTEMPT VIOLATIONS for {diet_type}: "
                f"{', '.join(state['_last_violations'])} — ABSOLUTELY DO NOT include these.\n"
            )

        # Cooking time
        max_time = profile.get("cooking_time_preference", "any")
        time_constraint = ""
        if max_time == "quick":
            time_constraint = "Total prep + cook time MUST be under 30 minutes."
        elif isinstance(max_time, int) and max_time > 0:
            time_constraint = f"Total time must not exceed {max_time} minutes."

        # Calorie goal
        calorie_target = profile.get("calorie_goal") or state.get("calorie_limit") or 400

        cuisine_prefs = profile.get("cuisine_preferences", [])
        cuisine = state.get("cuisine_preference") or (cuisine_prefs[0] if cuisine_prefs else "Indian")
        servings = state.get("servings", 2)
        pantry = ", ".join(state.get("available_ingredients", [])[:20]) or "Common staples"
        query = state.get("user_query", "")

        return f"""You are an expert Indian chef creating a personalised recipe.

═══ USER PROFILE ═══
{get_profile_context_string(profile)}

═══ ABSOLUTE CONSTRAINTS — NEVER VIOLATE ═══
{diet_constraints}{allergy_block}{egg_note}{health_block}
{retry_block}
═══ REQUEST ═══
"{query}"

═══ PANTRY ═══
{pantry}

═══ PARAMETERS ═══
Cuisine: {cuisine} | Target calories: ≤{calorie_target} kcal/serving | Serves: {servings}
{time_constraint}
Currency: {cur}

FORMAT YOUR RESPONSE EXACTLY AS:

## 🍽️ [Recipe Name]

**Description:** [2 sentences explaining why this suits the user's profile]

### 📋 Ingredients
- [quantity] [unit] [ingredient] (~{cur}X)

### 👨‍🍳 Instructions
1. [Step — include exact timings in parentheses e.g. (3 min)]

### 📊 Nutrition (per serving)
| Nutrient | Amount |
|----------|--------|
| Calories | X kcal |
| Protein | Xg |
| Carbs | Xg |
| Fat | Xg |
| Fiber | Xg |

### ⏱️ Time & Servings
- **Prep:** X min | **Cook:** X min | **Total:** X min | **Serves:** {servings}

### 💡 Chef's Tips
1. [Practical tip relevant to the user's health/diet]
2. [Second tip]

Make the recipe genuinely delicious and perfectly tailored to the profile above."""

    def _extract_ingredients(self, recipe: str) -> list:
        """Extract structured ingredients from recipe text."""
        ingredients = []
        in_ingredients = False
        
        for line in recipe.split('\n'):
            line = line.strip()
            if '### 📋 Ingredients' in line:
                in_ingredients = True
                continue
            if in_ingredients:
                if line.startswith('###') or line.startswith('##'):
                    break
                # Match ingredient lines like "- 250g paneer (~₹120)"
                match = re.match(r'[-•]\s*([\d.]+)\s*([a-zA-Z]+)\s+([a-zA-Z\s]+?)(?:\s*\(~[^)]+\))?$', line)
                if match:
                    qty = float(match.group(1))
                    unit = match.group(2)
                    name = match.group(3).strip()
                    ingredients.append({
                        "name": name,
                        "quantity": qty,
                        "unit": unit
                    })
        
        return ingredients

    def _extract_nutrition_from_recipe(self, recipe: str) -> dict:
        """Extract nutrition values from recipe text."""
        nutrition = {}
        
        # Try to find nutrition table
        cal_match = re.search(r'Calories\s*\|\s*(\d+)\s*kcal', recipe, re.IGNORECASE)
        if cal_match:
            nutrition["calories"] = int(cal_match.group(1))
        
        protein_match = re.search(r'Protein\s*\|\s*(\d+)g', recipe, re.IGNORECASE)
        if protein_match:
            nutrition["protein_g"] = float(protein_match.group(1))
        
        carbs_match = re.search(r'Carbs\s*\|\s*(\d+)g', recipe, re.IGNORECASE)
        if carbs_match:
            nutrition["carbs_g"] = float(carbs_match.group(1))
        
        fat_match = re.search(r'Fat\s*\|\s*(\d+)g', recipe, re.IGNORECASE)
        if fat_match:
            nutrition["fat_g"] = float(fat_match.group(1))
        
        fiber_match = re.search(r'Fiber\s*\|\s*(\d+)g', recipe, re.IGNORECASE)
        if fiber_match:
            nutrition["fiber_g"] = float(fiber_match.group(1))
        
        return nutrition

    def _check_violations(self, recipe: str, diet_type: str, allergies: list) -> list:
        violations = []
        rl = recipe.lower()

        # Diet violations
        forbidden = FORBIDDEN.get(diet_type.lower(), [])
        for f in forbidden:
            if f in rl:
                # Skip false positives like "chicken" in "chickpea"
                if f == "chicken" and "chickpea" in rl:
                    continue
                violations.append(f)

        # Indian vegetarian egg check
        if diet_type and "vegetarian" in diet_type.lower() and "non" not in diet_type.lower():
            for e in INDIAN_VEG_EXCLUDE:
                if e in rl:
                    violations.append(e)

        # Allergy violations
        for allergen in allergies:
            al = allergen.lower()
            if al == "nuts" or al == "nut":
                nut_words = ["almond", "cashew", "pistachio", "walnut", "peanut",
                             "hazelnut", "pecan", "nut butter", "marzipan", "nut oil"]
                for nw in nut_words:
                    if nw in rl:
                        violations.append(nw)
            elif al in rl:
                violations.append(al)

        return violations

    def _check_ingredient_violations(self, ingredients: list, diet_type: str, allergies: list) -> list:
        """Check structured ingredients for violations."""
        violations = []
        
        if not ingredients:
            return violations
        
        forbidden = FORBIDDEN.get(diet_type.lower(), [])
        
        for ing in ingredients:
            name = ing.get("name", "").lower()
            
            # Check diet violations
            for f in forbidden:
                if f in name:
                    if f == "chicken" and "chickpea" in name:
                        continue
                    violations.append(f)
            
            # Check egg for vegetarians
            if diet_type and "vegetarian" in diet_type.lower():
                for e in INDIAN_VEG_EXCLUDE:
                    if e in name:
                        violations.append(e)
            
            # Check allergies
            for allergen in allergies:
                al = allergen.lower()
                if al == "nuts" and any(n in name for n in ["almond", "cashew", "walnut", "peanut"]):
                    violations.append(name)
                elif al in name:
                    violations.append(name)
        
        return list(set(violations))


def recipe_agent(state: AgentState, client=None) -> AgentState:
    return RecipeAgent().run(state, client=client)