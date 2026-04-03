"""app.py — NutriBot v5.0 — Complete implementation with all features."""

import os
import sys
import uuid
import re
from datetime import datetime, timedelta, date

import streamlit as st
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv()

st.set_page_config(
    page_title="NutriBot · Smart Meal Assistant",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=DM+Sans:ital,wght@0,400;0,500;1,400&display=swap');

* { font-family: 'DM Sans', sans-serif; }
h1,h2,h3,.chef-wordmark { font-family: 'Sora', sans-serif !important; }

/* ── Scrollable chat area ── */
.chat-scroll { max-height: 65vh; overflow-y: auto; padding: 0 0.5rem; }

/* ── User bubble ── */
.user-bubble { display:flex; justify-content:flex-end; margin:0.6rem 0; }
.user-inner {
    background: linear-gradient(135deg, #e8541e 0%, #f97316 100%);
    color: white; padding: 0.7rem 1.1rem; border-radius: 20px 20px 4px 20px;
    max-width: 72%; font-size:0.93rem; line-height:1.55; font-weight:500;
    box-shadow: 0 4px 15px rgba(232,84,30,0.25);
}

/* ── AI bubble ── */
.ai-bubble { display:flex; gap:10px; margin:0.6rem 0; align-items:flex-start; }
.ai-avatar {
    width:38px; height:38px; min-width:38px;
    background: linear-gradient(135deg, #fff7ed, #fef3c7);
    border: 1.5px solid #fed7aa; border-radius:50%;
    display:flex; align-items:center; justify-content:center; font-size:1.1rem;
    box-shadow: 0 2px 8px rgba(232,84,30,0.15);
}
.ai-inner {
    background: #fafaf8; border: 1px solid #e8e5e0;
    border-radius: 4px 20px 20px 20px; padding: 0.8rem 1.1rem;
    max-width: 88%; font-size:0.93rem; line-height:1.6;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

/* ── Intent tags ── */
.intent-tag {
    display:inline-block; font-size:0.6rem; padding:2px 9px;
    border-radius:20px; margin-bottom:6px; font-weight:700;
    text-transform:uppercase; letter-spacing:0.06em; font-family:'Sora',sans-serif;
}
.tag-generate-recipe,.tag-generate_recipe{background:#fef3c7;color:#b45309}
.tag-smart-recommendation,.tag-smart_recommendation{background:#ede9fe;color:#6d28d9}
.tag-add-inventory,.tag-add_inventory{background:#d1fae5;color:#065f46}
.tag-view-inventory,.tag-view_inventory{background:#dbeafe;color:#1e40af}
.tag-health-advice,.tag-health_advice{background:#fce7f3;color:#9d174d}
.tag-memory-recall,.tag-memory_recall{background:#e0f2fe;color:#075985}
.tag-meal-plan,.tag-meal_plan{background:#f0fdf4;color:#166534}
.tag-shopping-list,.tag-shopping_list{background:#fdf4ff;color:#7e22ce}
.tag-daily-nutrition,.tag-daily_nutrition{background:#fff7ed;color:#c2410c}
.tag-save-meal,.tag-save_meal{background:#f0fdf4;color:#15803d}
.tag-rate-recipe,.tag-rate_recipe{background:#fef9c3;color:#a16207}
.tag-eco-tips,.tag-eco_tips{background:#dcfce7;color:#15803d}
.tag-budget-analysis,.tag-budget_analysis{background:#fff7ed;color:#c2410c}
.tag-cooking-tips,.tag-cooking_tips{background:#faf5ff;color:#7e22ce}
.tag-greeting{background:#fef9c3;color:#92400e}
.tag-general{background:#f1f5f9;color:#475569}

/* ── Pipeline panel ── */
.agent-panel {
    background: #fafaf8; border: 1px solid #e8e5e0; border-radius:14px;
    padding: 0.85rem; font-size:0.72rem; position:sticky; top:1rem;
}
.agent-panel-title {
    font-weight:800; color:#1a1a18; margin-bottom:0.6rem;
    font-size:0.65rem; text-transform:uppercase; letter-spacing:0.08em;
    font-family:'Sora',sans-serif;
}
.agent-row { display:flex; align-items:center; gap:7px; padding:3px 0; }
.agent-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.dot-idle{background:#e2e8f0} .dot-running{background:#f97316;animation:pulse .7s infinite}
.dot-done{background:#10b981} .dot-error{background:#ef4444}
.agent-name-idle{color:#94a3b8} .agent-name-running{color:#f97316;font-weight:700}
.agent-name-done{color:#10b981;font-weight:600} .agent-name-error{color:#ef4444}
.agent-time{margin-left:auto;color:#cbd5e1;font-size:0.62rem}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.35}}

/* ── Stream cursor ── */
.stream-cursor::after{content:'▋';animation:blink 1s infinite;color:#e8541e;font-size:0.8rem}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}

/* ── Cards ── */
.card {
    background:white; border:1px solid #e8e5e0; border-radius:14px;
    padding:1rem 1.1rem; margin:0.5rem 0;
    box-shadow:0 2px 10px rgba(0,0,0,0.04);
}
.card-title {
    font-size:0.65rem; font-weight:800; color:#64748b; text-transform:uppercase;
    letter-spacing:0.08em; margin-bottom:0.7rem; font-family:'Sora',sans-serif;
}
.metric-grid { display:grid; gap:0.4rem; }
.metric-cell {
    text-align:center; background:#fafaf8; border-radius:10px;
    padding:0.5rem 0.3rem; border:1px solid #f0ede8;
}
.metric-val{font-size:1.15rem;font-weight:800;font-family:'Sora',sans-serif}
.metric-lbl{font-size:0.58rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em}

/* ── Welcome card ── */
.welcome-card {
    background: linear-gradient(135deg, #fff7ed 0%, #fef3c7 50%, #fef9c3 100%);
    border: 1.5px solid #fed7aa; border-radius:20px; padding:1.8rem;
    margin:0.8rem 0; box-shadow:0 4px 20px rgba(232,84,30,0.1);
}
.welcome-title{font-size:1.5rem;font-weight:800;color:#c2410c;margin-bottom:0.4rem;font-family:'Sora',sans-serif}

/* ── Header ── */
.chef-wordmark{font-size:1.7rem;font-weight:800;color:#e8541e;line-height:1.1}
.chef-tagline{font-size:0.72rem;color:#94a3b8;font-weight:500;letter-spacing:0.03em}

/* ── Chip buttons ── */
.stButton button {
    border-radius:12px !important; font-weight:600 !important;
    font-family:'DM Sans',sans-serif !important;
}

/* ── Sidebar metric ── */
[data-testid="metric-container"] { background:#fafaf8; border-radius:10px; padding:0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Service initialization ────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def init_services():
    from groq import Groq
    from database.grocery_db import GroceryDatabase
    from database.feedback_db import FeedbackDatabase
    from tools.tools import load_recipe_dataset, build_recipe_knowledge_base
    from agents.user_profile import UserProfileDB
    from agents.pantry_agent import PantryAgent
    from agents.cooking_agent import CookingAgent
    from agents.memory_agent import MemoryAgent

    try:
        from agents.receipe_agent import RecipeAgent
    except ImportError:
        class RecipeAgent:
            def run(self, state, **kw):
                state["generated_recipe"] = "Recipe agent unavailable."
                return state

    groq_key = os.getenv("GROQ_API_KEY", "")
    client = Groq(api_key=groq_key) if groq_key else None

    db = GroceryDatabase(db_path=os.path.join(ROOT, "data", "grocery_inventory.db"))
    profile_db = UserProfileDB(db_path=os.path.join(ROOT, "data", "user_profile.db"))
    feedback_db = FeedbackDatabase(db_path=os.path.join(ROOT, "data", "feedback.db"))

    try:
        from services.price_service import PriceService
        price_service = PriceService()
    except ImportError:
        class _PS:
            def get_cheapest_protein(self, *a): return {"name": "lentil", "price_per_kg": 80, "protein_per_100g": 24}
        price_service = _PS()

    dataset = load_recipe_dataset()
    recipe_kb = build_recipe_knowledge_base(dataset)

    return {
        "client": client, "db": db, "recipe_kb": recipe_kb,
        "profile_db": profile_db, "feedback_db": feedback_db,
        "price_service": price_service,
        "pantry_agent": PantryAgent(),
        "cooking_agent": CookingAgent(),
        "memory_agent": MemoryAgent(),
    }


def init_session():
    defaults = {
        "chat_history": [], "turn_count": 0, "chip_query": None,
        "input_mode": "text", "session_id": str(uuid.uuid4())[:8],
        "cooking_mode": False, "current_recipe": None, "current_step": 0,
        "last_recipe": None, "last_nutrition": None, "last_budget": None, "last_eco": None,
        "prefs": {
            "dietary": [], "health": [], "cuisine": "Indian",
            "calories": 500, "budget": 500, "servings": 2,
        },
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Card renderers ────────────────────────────────────────────────────────────
def _cell(val, label, color, cols=4):
    return (
        f'<div class="metric-cell">'
        f'<div class="metric-val" style="color:{color}">{val}</div>'
        f'<div class="metric-lbl">{label}</div>'
        f'</div>'
    )


def render_nutrition_card(nutrition_data: dict) -> str:
    if not nutrition_data:
        return ""
    ps = nutrition_data.get("per_serving", {})
    cal = ps.get("calories", 0)
    prot = ps.get("protein_g", 0)
    carbs = ps.get("carbs_g", 0)
    fat = ps.get("fat_g", 0)
    fiber = ps.get("fiber_g", 0)
    sodium = ps.get("sodium_mg", 0)
    usda = nutrition_data.get("usda_matched", 0)
    total_i = max(nutrition_data.get("total_ingredients", 1), 1)
    acc = round(usda / total_i * 100)
    acc_color = "#059669" if acc > 70 else "#d97706" if acc > 40 else "#dc2626"
    badge_bg = "#d1fae5" if acc > 70 else "#fef3c7" if acc > 40 else "#fee2e2"

    return f"""
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.7rem">
    <span class="card-title">📊 Nutrition Per Serving</span>
    <span style="font-size:0.6rem;padding:2px 9px;border-radius:20px;background:{badge_bg};color:{acc_color};font-weight:700">{acc}% USDA</span>
  </div>
  <div class="metric-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:0.4rem">
    {_cell(f"{cal:.0f}", "kcal", "#f97316")}
    {_cell(f"{prot:.0f}g", "protein", "#3b82f6")}
    {_cell(f"{carbs:.0f}g", "carbs", "#10b981")}
    {_cell(f"{fat:.0f}g", "fat", "#8b5cf6")}
  </div>
  <div class="metric-grid" style="grid-template-columns:repeat(2,1fr)">
    {_cell(f"{fiber:.0f}g", "fiber", "#059669")}
    {_cell(f"{sodium:.0f}mg", "sodium", "#c2410c")}
  </div>
</div>"""


def render_budget_card(budget: dict) -> str:
    if not budget:
        return ""
    cur = budget.get("currency", "₹")
    total = budget.get("total_cost", 0)
    per_srv = budget.get("per_serving", 0)
    within = budget.get("within_budget", True)
    limit = budget.get("budget_limit", 500)
    status_color = "#059669" if within else "#dc2626"
    status_text = "✅ Within Budget" if within else "⚠️ Over Budget"
    bar_pct = min(100, round(total / max(limit, 1) * 100))
    bar_color = "#10b981" if within else "#ef4444"

    return f"""
<div class="card">
  <span class="card-title">💰 Cost Estimate</span>
  <div class="metric-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:0.6rem">
    {_cell(f"{cur}{total:.0f}", "total", "#f97316")}
    {_cell(f"{cur}{per_srv:.0f}", "per serving", "#3b82f6")}
    <div class="metric-cell"><div class="metric-val" style="color:{status_color};font-size:0.75rem">{status_text}</div><div class="metric-lbl">vs {cur}{limit:.0f} budget</div></div>
  </div>
  <div style="background:#f1f5f9;border-radius:6px;height:6px;overflow:hidden">
    <div style="width:{bar_pct}%;height:100%;background:{bar_color};border-radius:6px;transition:width .5s"></div>
  </div>
  <div style="font-size:0.65rem;color:#94a3b8;margin-top:3px">{bar_pct}% of weekly budget used</div>
</div>"""


def render_eco_card(eco: dict) -> str:
    if not eco:
        return ""
    score = eco.get("score", 0)
    grade = eco.get("grade", "C")
    co2 = eco.get("co2_kg", 0)
    co2_saved = eco.get("co2_saved_kg", 0)
    tip = eco.get("tip", "")
    used = eco.get("expiring_used", 0)
    color = "#059669" if score >= 75 else "#f97316" if score >= 50 else "#dc2626"
    grade_bg = {"A+": "#d1fae5", "A": "#d1fae5", "B": "#fef3c7", "C": "#fff7ed", "D": "#fee2e2"}.get(grade, "#f1f5f9")

    return f"""
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <span class="card-title">🌱 Eco Score</span>
    <div style="text-align:right">
      <span style="font-size:1.5rem;font-weight:800;color:{color};font-family:'Sora',sans-serif">{score:.0f}</span>
      <span style="font-size:0.7rem;color:#94a3b8">/100</span>
      <span style="display:block;font-size:0.65rem;background:{grade_bg};color:{color};padding:1px 7px;border-radius:20px;font-weight:700">Grade {grade}</span>
    </div>
  </div>
  <div class="metric-grid" style="grid-template-columns:1fr 1fr;margin:0.5rem 0">
    {_cell(f"{co2:.2f}kg", "CO₂ used", "#64748b")}
    {_cell(f"{co2_saved:.2f}kg", "CO₂ saved", "#059669")}
  </div>
  {f'<div style="font-size:0.75rem;color:#059669;margin-top:0.3rem">🎉 Used {used} expiring item(s)</div>' if used else ''}
  <div style="font-size:0.75rem;color:#64748b;margin-top:0.3rem;font-style:italic">{tip}</div>
</div>"""


def render_pipeline_panel(agent_status: dict):
    AGENTS = [
        "🧠 Memory Agent", "🎯 Intent Agent", "🥕 Pantry Agent",
        "🍳 Recipe Agent", "📊 Nutrition Agent", "💰 Budget Agent",
        "🌱 Eco Agent", "🏥 Health Agent", "📅 Meal Planner",
        "🛒 Shopping Agent", "⭐ Taste Agent",
    ]
    lines = ['<div class="agent-panel">', '<div class="agent-panel-title">⚡ Live Pipeline</div>']
    for agent in AGENTS:
        info = agent_status.get(agent, {})
        status = info.get("status", "idle")
        t = info.get("time", 0)
        t_str = f'<span class="agent-time">{t:.1f}s</span>' if t else ""
        dot = {"idle": "dot-idle", "running": "dot-running", "done": "dot-done", "error": "dot-error"}.get(status, "dot-idle")
        nm = {"idle": "agent-name-idle", "running": "agent-name-running", "done": "agent-name-done", "error": "agent-name-error"}.get(status, "agent-name-idle")
        lines.append(f'<div class="agent-row"><div class="agent-dot {dot}"></div><span class="{nm}">{agent}</span>{t_str}</div>')
    lines.append("</div>")
    st.markdown("".join(lines), unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(services):
    with st.sidebar:
        st.markdown("## ⚙️ Settings")

        profile = services["profile_db"].get_full_profile()
        if profile:
            with st.expander("🧠 Your Profile", expanded=False):
                diet = profile.get("diet_type", "—")
                goal = (profile.get("fitness_goal") or "—").replace("_", " ").title()
                cp = profile.get("cuisine_preferences", [])
                cuisine = cp[0] if isinstance(cp, list) and cp else "—"
                bp = profile.get("budget_preference", {})
                cur = "₹" if isinstance(bp, dict) and bp.get("currency") == "INR" else "₹"
                amt = bp.get("amount", 500) if isinstance(bp, dict) else 500

                st.markdown(f"""
| Field | Value |
|-------|-------|
| 🥗 Diet | {diet} |
| 🎯 Goal | {goal} |
| 🍽️ Cuisine | {cuisine} |
| 💰 Budget | {cur}{amt}/week |
| 🔥 Calories | {profile.get("calorie_goal", "—")} kcal/meal |
                """)
                if profile.get("health_conditions"):
                    st.caption(f"🏥 Health: {', '.join(profile['health_conditions'])}")
                if profile.get("allergies"):
                    st.caption(f"⚠️ Allergies: {', '.join(profile['allergies'])}")
                if st.button("🗑️ Reset Profile", use_container_width=True):
                    services["profile_db"].clear()
                    st.success("Profile cleared!")
                    st.rerun()
        else:
            st.info("💡 Tell me your diet & goals in chat to build your profile!")

        with st.expander("🥗 Dietary Preferences", expanded=True):
            p = st.session_state["prefs"]
            p["dietary"] = st.multiselect("Diet", ["Vegetarian", "Vegan", "Non-Vegetarian", "Keto", "Paleo"], default=p["dietary"], label_visibility="collapsed")
            p["health"] = st.multiselect("Health", ["Diabetes", "Hypertension", "High Cholesterol", "Celiac"], default=p["health"], label_visibility="collapsed")

        with st.expander("💰 Budget & Goals", expanded=True):
            p["cuisine"] = st.selectbox("Cuisine", ["Indian", "Italian", "Asian", "Mediterranean", "Mexican", "American"])
            p["calories"] = st.slider("Calories per meal", 300, 800, p["calories"], 50)
            p["budget"] = st.number_input("Weekly budget (₹)", 200, 3000, p["budget"], 50)
            p["servings"] = st.number_input("Servings", 1, 6, p["servings"])
        st.session_state["prefs"] = p

        st.divider()

        # Pantry stats
        groceries = services["db"].get_all_groceries()
        expiring = services["db"].get_expiring_soon(days=3)
        c1, c2 = st.columns(2)
        with c1: st.metric("🥬 Pantry", len(groceries))
        with c2: st.metric("⚠️ Expiring", len(expiring))

        if expiring:
            with st.expander(f"🔔 Expiring ({len(expiring)})", expanded=True):
                for item in expiring[:5]:
                    exp = item.get("expiry_date", "")
                    try:
                        days_left = (datetime.fromisoformat(exp) - datetime.now()).days
                        badge = "🔴" if days_left <= 1 else "🟡"
                    except Exception:
                        badge = "🟡"
                        days_left = "?"
                    st.markdown(f"{badge} **{item['item_name'].title()}** — {days_left}d left")

        # Last recipe quick actions
        if st.session_state.get("last_recipe"):
            st.divider()
            st.markdown("**🍳 Last Recipe**")
            last = st.session_state["last_recipe"]
            name_match = re.search(r"##\s*🍽️\s*(.+)", last)
            recipe_name = name_match.group(1).strip() if name_match else "Last Recipe"
            st.caption(recipe_name)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🍳 Cook", use_container_width=True, key="sb_cook"):
                    st.session_state["cooking_mode"] = True
                    st.session_state["current_recipe"] = last
                    st.session_state["current_step"] = 0
                    st.rerun()
            with c2:
                if st.button("💾 Save", use_container_width=True, key="sb_save"):
                    st.session_state["chip_query"] = "save this as dinner"

        st.divider()
        # Feedback stats
        try:
            stats = services["feedback_db"].get_preference_summary()
            if stats["total_rated"] > 0:
                st.metric("⭐ Avg Rating", f"{stats['avg_rating']}/5",
                         f"{stats['total_rated']} recipes rated")
        except Exception:
            pass

        st.divider()
        groq_ok = bool(os.getenv("GROQ_API_KEY"))
        anthropic_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
        st.markdown(
            f"**API Status**  \n"
            f"{'✅' if groq_ok else '❌'} Groq (LLM + Voice)  \n"
            f"{'✅' if anthropic_ok else '⚠️'} Claude Vision"
        )

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.update({"chat_history": [], "turn_count": 0})
            st.rerun()

# Add these functions to your existing app.py

def render_voice_section(client):
    """Render voice input section with Google-like assistant."""
    import streamlit as st
    from voice.voice_agent import render_voice_input_ui
    
    st.markdown("---")
    st.markdown("### 🎙️ Voice Assistant")
    
    voice_text = render_voice_input_ui(client)
    if voice_text:
        return voice_text
    return None


def render_image_section(db, client):
    """Render image input section for grocery scanning."""
    import streamlit as st
    from vision.vision_agent import render_image_input_ui
    
    st.markdown("### 📸 Smart Scan")
    
    result = render_image_input_ui(db, client)
    if result:
        return result
    return None


def render_bill_processor(db, client):
    """Specialized bill/receipt processor."""
    import streamlit as st
    from vision.vision_agent import process_bill_image, preprocess_image
    
    st.markdown("### 🧾 Bill/Receipt Scanner")
    st.markdown("*Upload a grocery bill photo - I'll add all items to your pantry!*")
    
    bill_file = st.file_uploader(
        "Upload bill/receipt photo", 
        type=["jpg", "jpeg", "png"],
        key="bill_upload"
    )
    
    if bill_file:
        st.image(bill_file, caption="Your receipt", width=200)
        if st.button("📝 Process Bill", type="primary"):
            raw_bytes = bill_file.read()
            img_bytes, _ = preprocess_image(raw_bytes)
            with st.spinner("📄 Reading bill..."):
                result, summary = process_bill_image(img_bytes, db, client)
            st.markdown(summary)
            return summary
    return None


# ── Chat history renderer ─────────────────────────────────────────────────────
def render_history():
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            icon = {"voice": "🎙️ ", "image": "📸 "}.get(msg.get("mode", "text"), "")
            st.markdown(
                f'<div class="user-bubble"><div class="user-inner">{icon}{msg["content"]}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            intent = msg.get("intent", "general")
            tag_cls = f"tag-{intent.replace('_', '-')}"
            st.markdown(
                f'<div class="ai-bubble"><div class="ai-avatar">🥗</div><div class="ai-inner">'
                f'<div class="intent-tag {tag_cls}">{intent.replace("_"," ").title()}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(msg["content"])
            # Replay cards
            if msg.get("nutrition_data"):
                st.markdown(render_nutrition_card(msg["nutrition_data"]), unsafe_allow_html=True)
            if msg.get("budget_data"):
                st.markdown(render_budget_card(msg["budget_data"]), unsafe_allow_html=True)
            if msg.get("eco_data"):
                st.markdown(render_eco_card(msg["eco_data"]), unsafe_allow_html=True)
            # Rating widget (only for recipe messages without rating yet)
            if msg.get("show_rating") and not msg.get("rated"):
                cols = st.columns(5)
                for i, col in enumerate(cols, 1):
                    with col:
                        if st.button("⭐" * i, key=f"rate_{msg.get('msg_id','')}_star{i}"):
                            msg["rated"] = True
                            st.session_state["chip_query"] = f"rate {i} stars"
                            st.rerun()
            st.markdown("</div></div>", unsafe_allow_html=True)


# ── Main pipeline runner ──────────────────────────────────────────────────────
def run_pipeline(prompt: str, services) -> dict:
    from agents.streaming_pipeline import run_streaming_pipeline
    from agents.workflow import build_initial_state

    p = st.session_state["prefs"]
    state = build_initial_state(
        user_query=prompt,
        dietary_restrictions=[d.lower() for d in p["dietary"]],
        health_conditions=[h.lower() for h in p["health"]],
        calorie_limit=p["calories"],
        budget_limit=float(p["budget"]),
        servings=p["servings"],
        cuisine_preference=p["cuisine"],
        extra_ingredients=[],
        conversation_history=st.session_state["chat_history"].copy(),
    )
    state["session_id"] = st.session_state["session_id"]

    left_col, right_col = st.columns([1, 2.5])

    agent_status = {}
    pipeline_ph = left_col.empty()
    with pipeline_ph.container():
        render_pipeline_panel(agent_status)

    right_col.markdown(
        '<div class="ai-bubble"><div class="ai-avatar">🥗</div><div class="ai-inner">',
        unsafe_allow_html=True,
    )

    intent_ph = right_col.empty()
    response_ph = right_col.empty()

    accumulated = ""
    final_state = state

    for event in run_streaming_pipeline(
        state, services["client"], services["db"], services["recipe_kb"],
        profile_db=services["profile_db"], feedback_db=services["feedback_db"],
    ):
        etype = event.get("type")

        if etype == "phase":
            agent = event["agent"]
            agent_status[agent] = {"status": event["status"], "time": event.get("time", 0)}
            with pipeline_ph.container():
                render_pipeline_panel(agent_status)
            if agent == "🎯 Intent Agent" and event.get("intent"):
                intent = event["intent"]
                tc = f"tag-{intent.replace('_', '-')}"
                intent_ph.markdown(
                    f'<div class="intent-tag {tc}">{intent.replace("_", " ").title()}</div>',
                    unsafe_allow_html=True,
                )

        elif etype == "token":
            accumulated += event["text"]
            response_ph.markdown(accumulated + '<span class="stream-cursor"></span>', unsafe_allow_html=True)

        elif etype == "section":
            title = event["title"]
            content = event["content"]
            if "Budget" in title and isinstance(content, dict):
                right_col.markdown(render_budget_card(content), unsafe_allow_html=True)
            elif "Nutrition" in title and isinstance(content, dict):
                right_col.markdown(render_nutrition_card(content), unsafe_allow_html=True)
            elif "Eco" in title and isinstance(content, dict):
                right_col.markdown(render_eco_card(content), unsafe_allow_html=True)
            elif "Health" in title and content and "✅" not in str(content):
                right_col.warning(str(content)[:300])

        elif etype == "complete":
            final_state = event["state"]
            if accumulated:
                response_ph.markdown(accumulated, unsafe_allow_html=True)

    right_col.markdown("</div></div>", unsafe_allow_html=True)
    return final_state


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_session()

    with st.spinner("🥗 Loading NutriBot..."):
        services = init_services()

    if not os.getenv("GROQ_API_KEY"):
        st.error("⚠️ Set `GROQ_API_KEY` in your `.env` file. Free at console.groq.com")
        st.stop()

    render_sidebar(services)

    # ── Header ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1])
    with c1:
        st.markdown(
            '<div class="chef-wordmark">🥗 NutriBot</div>'
            '<div class="chef-tagline">Smart Meal Assistant · Track · Cook · Save</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.metric("💬 Turns", st.session_state["turn_count"])
    with c3:
        st.metric("📦 Pantry", len(services["db"].get_all_groceries()))
    with c4:
        exp = services["db"].get_expiring_soon(3)
        color = "#ef4444" if exp else "#10b981"
        st.markdown(
            f'<div style="text-align:center;padding:0.4rem">'
            f'<div style="font-size:1.6rem;font-weight:800;color:{color};font-family:Sora,sans-serif">{len(exp)}</div>'
            f'<div style="font-size:0.68rem;color:#94a3b8">Expiring</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr style="border:none;border-top:1px solid #e8e5e0;margin:0.5rem 0">', unsafe_allow_html=True)

    # ── Cooking mode ──────────────────────────────────────────────────────────
    if st.session_state.get("cooking_mode") and st.session_state.get("current_recipe"):
        try:
            from agents.cooking_agent import CookingAgent
            cooking_agent = CookingAgent()
            steps = cooking_agent.parse_recipe_steps(st.session_state["current_recipe"])

            if steps:
                idx = st.session_state.get("current_step", 0)
                total = len(steps)
                st.markdown("---")
                st.markdown(f"### 🍳 Cooking Mode — Step {idx + 1} of {total}")
                progress = (idx) / max(total, 1)
                st.progress(progress)

                current = steps[idx]
                st.markdown(
                    f'<div class="card" style="font-size:1.1rem;line-height:1.7">'
                    f'<div style="font-size:0.65rem;color:#e8541e;font-weight:800;text-transform:uppercase;margin-bottom:0.4rem">Step {idx+1}</div>'
                    f'{current["instruction"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if current.get("timer_seconds"):
                    mins = current["timer_seconds"] // 60
                    secs = current["timer_seconds"] % 60
                    timer_html = f"""
                    <div style="text-align:center;padding:1rem;background:#fff7ed;border-radius:12px;margin:0.5rem 0">
                        <div style="font-size:2.5rem;font-family:monospace;font-weight:800;color:#e8541e" id="timer-{idx}">{mins}:{secs:02d}</div>
                        <button onclick="startTimer_{idx}()" style="background:#e8541e;color:white;border:none;padding:8px 24px;border-radius:8px;cursor:pointer;font-weight:600;margin-top:0.5rem">▶ Start Timer</button>
                    </div>
                    <script>
                    function startTimer_{idx}(){{
                        let rem={current["timer_seconds"]};
                        const d=document.getElementById('timer-{idx}');
                        const t=setInterval(()=>{{rem--;const m=Math.floor(rem/60),s=rem%60;d.textContent=`${{m}}:${{String(s).padStart(2,'0')}}`;if(rem<=0){{clearInterval(t);d.textContent='Done! ✅';d.style.color='#059669';}}}},1000);
                    }}
                    </script>"""
                    st.components.v1.html(timer_html, height=130)

                c1, c2, c3 = st.columns(3)
                with c1:
                    if idx > 0 and st.button("⏮ Previous", use_container_width=True):
                        st.session_state["current_step"] -= 1
                        st.rerun()
                with c2:
                    if st.button("✕ Exit Cooking Mode", use_container_width=True):
                        st.session_state["cooking_mode"] = False
                        st.rerun()
                with c3:
                    if idx < total - 1:
                        if st.button("Next Step ⏭", use_container_width=True, type="primary"):
                            st.session_state["current_step"] += 1
                            st.rerun()
                    else:
                        if st.button("🎉 Complete!", use_container_width=True, type="primary"):
                            st.balloons()
                            st.session_state["cooking_mode"] = False
                            st.session_state["chip_query"] = "rate the recipe I just cooked"
                            st.rerun()
                st.markdown("---")
        except Exception as e:
            st.error(f"Cooking mode error: {e}")
            st.session_state["cooking_mode"] = False

    # ── Welcome screen ────────────────────────────────────────────────────────
    if not st.session_state["chat_history"]:
        st.markdown("""
        <div class="welcome-card">
            <div class="welcome-title">Welcome to NutriBot 🥗</div>
            <p style="color:#78350f;margin:0.4rem 0">Your personal AI nutrition assistant that <strong>remembers you</strong>, tracks your pantry, plans meals, and guides you step-by-step while cooking.</p>
            <p style="color:#92400e;font-weight:600;margin-top:0.8rem">Try saying something like:</p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-top:0.5rem">
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">📦 "I bought 500g paneer, 1kg spinach"</div>
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">🍳 "Make me palak paneer"</div>
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">💬 "Hi, I'm vegetarian, trying to lose weight"</div>
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">📅 "Plan my meals for 3 days"</div>
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">📊 "Show my daily nutrition"</div>
                <div style="background:rgba(255,255,255,0.7);border-radius:10px;padding:0.5rem 0.7rem;font-size:0.85rem">💰 "What's the cheapest protein?"</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        CHIPS = [
            ("📦", "I bought groceries"),
            ("🍳", "What should I cook?"),
            ("📅", "Plan my week"),
            ("📊", "Today's nutrition"),
            ("🛒", "Build shopping list"),
            ("🌱", "Eco tips"),
        ]
        cols = st.columns(len(CHIPS))
        for i, (icon, text) in enumerate(CHIPS):
            with cols[i]:
                if st.button(f"{icon} {text}", key=f"chip_{i}", use_container_width=True):
                    st.session_state["chip_query"] = text

    # ── Chat history ──────────────────────────────────────────────────────────
    render_history()

    # ── Input area with enhanced options ─────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #e8e5e0;margin:0.8rem 0">', unsafe_allow_html=True)

    # Mode selection with more options
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("⌨️ Text", use_container_width=True,
                    type="primary" if st.session_state["input_mode"] == "text" else "secondary"):
            st.session_state["input_mode"] = "text"
            st.rerun()
    with col2:
        if st.button("🎙️ Voice", use_container_width=True,
                    type="primary" if st.session_state["input_mode"] == "voice" else "secondary"):
            st.session_state["input_mode"] = "voice"
            st.rerun()
    with col3:
        if st.button("📸 Photo", use_container_width=True,
                    type="primary" if st.session_state["input_mode"] == "image" else "secondary"):
            st.session_state["input_mode"] = "image"
            st.rerun()
    with col4:
        if st.button("🧾 Bill", use_container_width=True,
                    type="primary" if st.session_state["input_mode"] == "bill" else "secondary"):
            st.session_state["input_mode"] = "bill"
            st.rerun()
    with col5:
        if st.button("🎤 Assistant", use_container_width=True,
                    type="primary" if st.session_state["input_mode"] == "assistant" else "secondary"):
            st.session_state["input_mode"] = "assistant"
            st.rerun()


     # ── Gather prompt based on mode ─────────────────────────────────────────
    prompt = st.session_state.pop("chip_query", None)

    if st.session_state["input_mode"] == "text":
        typed = st.chat_input("Ask about recipes, pantry, nutrition, meal plans...")
        prompt = typed or prompt

    elif st.session_state["input_mode"] == "voice":
        voice_result = render_voice_section(services["client"])
        prompt = voice_result or prompt

    elif st.session_state["input_mode"] == "image":
        image_result = render_image_section(services["db"], services["client"])
        if image_result:
            prompt = image_result

    elif st.session_state["input_mode"] == "bill":
        bill_result = render_bill_processor(services["db"], services["client"])
        if bill_result:
            prompt = bill_result

    elif st.session_state["input_mode"] == "assistant":
        # Full voice assistant mode
        with st.expander("🎙️ Voice Assistant Active", expanded=True):
            from voice.voice_agent import render_voice_input_ui
            voice_text = render_voice_input_ui(services["client"])
            if voice_text:
                prompt = voice_text
                st.session_state["input_mode"] = "text"  # Reset after getting input

                
    # ── Process ───────────────────────────────────────────────────────────────
    if prompt and prompt.strip():
        mode_icon = {"voice": "🎙️ ", "image": "📸 "}.get(st.session_state["input_mode"], "")
        st.markdown(
            f'<div class="user-bubble"><div class="user-inner">{mode_icon}{prompt}</div></div>',
            unsafe_allow_html=True,
        )
        st.session_state["chat_history"].append({
            "role": "user", "content": prompt, "mode": st.session_state["input_mode"],
        })

        final_state = run_pipeline(prompt, services)

        intent = final_state.get("intent", "general")
        message = (
            final_state.get("assistant_message")
            or final_state.get("generated_recipe")
            or "I processed your request."
        )

        # Build history entry
        msg_id = str(uuid.uuid4())[:8]
        history_entry = {
            "role": "assistant", "content": message, "intent": intent, "msg_id": msg_id,
        }

        # Store card data for replay
        if final_state.get("nutrition_data"):
            history_entry["nutrition_data"] = final_state["nutrition_data"]
        if final_state.get("budget_analysis"):
            history_entry["budget_data"] = final_state["budget_analysis"]
        if final_state.get("eco_score"):
            history_entry["eco_data"] = final_state["eco_score"]

        # Show rating widget after recipe
        is_recipe = intent in ("generate_recipe", "smart_recommendation")
        if is_recipe:
            history_entry["show_rating"] = True
            st.session_state["last_recipe"] = final_state.get("generated_recipe", "")
            st.session_state["last_nutrition"] = final_state.get("nutrition_data")
            st.session_state["last_budget"] = final_state.get("budget_analysis")
            st.session_state["last_eco"] = final_state.get("eco_score")

        st.session_state["chat_history"].append(history_entry)
        st.session_state["turn_count"] += 1

        # Offer cooking mode for recipes
        if is_recipe and final_state.get("generated_recipe"):
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🍳 Start Cooking Mode", use_container_width=True, type="primary"):
                    st.session_state["cooking_mode"] = True
                    st.session_state["current_recipe"] = final_state["generated_recipe"]
                    st.session_state["current_step"] = 0
                    st.rerun()
            with c2:
                if st.button("💾 Save as Dinner", use_container_width=True):
                    st.session_state["chip_query"] = "save this as dinner"
                    st.rerun()
            with c3:
                if st.button("🛒 Shopping List", use_container_width=True):
                    st.session_state["chip_query"] = "shopping list for this recipe"
                    st.rerun()

        st.rerun()


if __name__ == "__main__":
    main()

# for Web based Dashboard
# c:\Users\HP\OneDrive\Desktop\mgm\venv\Scripts\Activate.ps1         
# streamlit run app.py       

# for Api starting
# c:\Users\HP\OneDrive\Desktop\mgm\venv\Scripts\Activate.ps1       
# cd backend  
# python main.py
