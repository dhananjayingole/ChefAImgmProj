"""Reusable UI components for NutriBot."""

import streamlit as st
import pandas as pd
import plotly.express as px


CHIPS = [
    ("📦", "I bought groceries"),
    ("🍳", "What should I cook?"),
    ("📅", "Plan my week"),
    ("🔔", "What's expiring?"),
    ("💪", "High protein recipes"),
    ("💰", "Budget friendly"),
]


def render_chat_message(msg: dict, idx: int, feedback_db=None):
    """Render a single chat message."""
    if msg["role"] == "user":
        mode_icon = {"voice": "🎙️ ", "image": "📸 "}.get(msg.get("mode", "text"), "")
        st.markdown(
            f'<div class="user-bubble"><div class="user-inner">{mode_icon}{msg["content"]}</div></div>',
            unsafe_allow_html=True
        )
    else:
        tag = f'<div class="intent-tag tag-{msg.get("intent", "general")}">{msg.get("intent", "general").replace("_", " ").title()}</div>'
        st.markdown(
            f'<div class="ai-bubble"><div class="ai-avatar">🥗</div><div class="ai-inner">{tag}',
            unsafe_allow_html=True
        )
        st.markdown(msg["content"])
        st.markdown("</div></div>", unsafe_allow_html=True)


def render_pipeline_panel(agent_status: dict):
    """Render live agent pipeline panel."""
    agents = [
        "🧠 Memory Agent", "🎯 Intent Agent", "🥕 Pantry Agent",
        "🍳 Recipe Agent", "💰 Budget Agent", "📊 Nutrition Agent",
        "🌱 Waste Agent", "⭐ Taste Agent", "🛒 Shopping Agent", "✅ QA Agent"
    ]
    
    lines = ['<div class="agent-panel">', '<div class="agent-panel-title">⚡ Live Pipeline</div>']
    
    for agent in agents:
        status = agent_status.get(agent, {}).get("status", "idle")
        time_val = agent_status.get(agent, {}).get("time", 0)
        time_str = f'<span class="agent-time">{time_val:.1f}s</span>' if time_val else ""
        
        dot_class = {
            "idle": "dot-idle", "running": "dot-running",
            "done": "dot-done", "error": "dot-error"
        }.get(status, "dot-idle")
        
        name_class = {
            "idle": "agent-name-idle", "running": "agent-name-running",
            "done": "agent-name-done", "error": "agent-name-error"
        }.get(status, "agent-name-idle")
        
        lines.append(
            f'<div class="agent-row">'
            f'<div class="agent-dot {dot_class}"></div>'
            f'<span class="{name_class}">{agent}</span>'
            f'{time_str}</div>'
        )
    
    lines.append("</div>")
    st.markdown("".join(lines), unsafe_allow_html=True)


def render_nutrition_card(nutrition: dict) -> str:
    """Render nutrition card HTML."""
    ps = nutrition.get("per_serving", {})
    cal = ps.get("calories", 0)
    protein = ps.get("protein_g", 0)
    carbs = ps.get("carbs_g", 0)
    fat = ps.get("fat_g", 0)
    fiber = ps.get("fiber_g", 0)
    
    return f"""
    <div class="nutrition-card">
        <div class="nutrition-header">📊 Nutrition Per Serving</div>
        <div class="nutrition-grid">
            <div class="nutrition-item">
                <div class="nutrition-value">{cal:.0f}</div>
                <div class="nutrition-label">kcal</div>
            </div>
            <div class="nutrition-item">
                <div class="nutrition-value">{protein:.0f}g</div>
                <div class="nutrition-label">protein</div>
            </div>
            <div class="nutrition-item">
                <div class="nutrition-value">{carbs:.0f}g</div>
                <div class="nutrition-label">carbs</div>
            </div>
            <div class="nutrition-item">
                <div class="nutrition-value">{fat:.0f}g</div>
                <div class="nutrition-label">fat</div>
            </div>
            <div class="nutrition-item">
                <div class="nutrition-value">{fiber:.0f}g</div>
                <div class="nutrition-label">fiber</div>
            </div>
        </div>
    </div>
    """


def render_budget_card(budget: dict) -> str:
    """Render budget card HTML."""
    cur = budget.get("currency", "₹")
    total = budget.get("total_cost", 0)
    per_serving = budget.get("per_serving", 0)
    within = budget.get("within_budget", True)
    status = "✅ Within Budget" if within else "⚠️ Over Budget"
    color = "#2ecc71" if within else "#e74c3c"
    
    return f"""
    <div class="budget-card">
        <div class="budget-header">💰 Budget</div>
        <div class="budget-grid">
            <div class="budget-item">
                <div class="budget-value">{cur}{total:.0f}</div>
                <div class="budget-label">Total</div>
            </div>
            <div class="budget-item">
                <div class="budget-value">{cur}{per_serving:.0f}</div>
                <div class="budget-label">Per Serving</div>
            </div>
            <div class="budget-item">
                <div class="budget-value" style="color:{color}">{status.split()[-1]}</div>
                <div class="budget-label">Status</div>
            </div>
        </div>
    </div>
    """


def render_eco_card(eco: dict) -> str:
    """Render eco score card HTML."""
    score = eco.get("score", 0)
    grade = eco.get("grade", "C")
    co2 = eco.get("co2_saved_kg", 0)
    tip = eco.get("tip", "")
    
    color = "#2ecc71" if score >= 70 else "#e8541e" if score >= 50 else "#e74c3c"
    
    return f"""
    <div class="eco-card">
        <div class="eco-header">🌱 Eco Impact</div>
        <div class="eco-score" style="color:{color}">{score:.0f}<span style="font-size:0.8rem">/100</span></div>
        <div class="eco-grade">Grade {grade}</div>
        <div class="eco-tip">{tip}</div>
        <div class="eco-metric">CO₂ Saved: {co2:.1f} kg</div>
    </div>
    """


def render_cooking_mode_ui(recipe_text: str, current_step: int = 0):
    """Render step-by-step cooking mode UI."""
    from agents.cooking_agent import CookingAgent
    
    cooking_agent = CookingAgent()
    steps = cooking_agent.parse_recipe_steps(recipe_text)
    
    if not steps:
        st.info("No steps found in this recipe. Use the recipe view instead.")
        return None
    
    if current_step >= len(steps):
        st.success("🎉 **Recipe complete!** Enjoy your meal!")
        if st.button("Exit Cooking Mode", use_container_width=True):
            return "exit"
        return None
    
    current = steps[current_step]
    
    st.markdown(f"""
    <div class="cooking-mode">
        <div class="cooking-header">🍳 Cooking Mode</div>
        <div class="step-progress">Step {current_step + 1} of {len(steps)}</div>
        <div class="step-instruction">{current['instruction']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if current.get("timer_seconds"):
        mins = current["timer_seconds"] // 60
        secs = current["timer_seconds"] % 60
        timer_html = cooking_agent.get_timer_js(current["timer_seconds"])
        st.components.v1.html(timer_html, height=150)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if current_step > 0:
            if st.button("⏮️ Previous", use_container_width=True):
                return "prev"
    with col2:
        if st.button("Exit Mode", use_container_width=True):
            return "exit"
    with col3:
        if st.button("Next Step ⏭️", use_container_width=True, type="primary"):
            return "next"
    
    return None