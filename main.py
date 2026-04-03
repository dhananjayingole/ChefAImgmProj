# backend/main.py
"""
NutriBot Backend API - FastAPI Server
Complete backend implementation for Android app integration
"""

import os
import sys
import uuid
import base64
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# Pydantic Models for API
# ============================================================================

class UserMessage(BaseModel):
    """User message request model"""
    query: str = Field(..., description="User's message/question")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User ID for profile persistence")
    input_mode: str = Field("text", description="Input mode: text, voice, image")
    
    # Optional context
    dietary_restrictions: Optional[List[str]] = Field(None, description="Dietary restrictions")
    health_conditions: Optional[List[str]] = Field(None, description="Health conditions")
    calorie_limit: Optional[int] = Field(500, description="Calorie limit per meal")
    budget_limit: Optional[float] = Field(500.0, description="Budget limit in INR")
    servings: Optional[int] = Field(2, description="Number of servings")
    cuisine_preference: Optional[str] = Field("Indian", description="Cuisine preference")


class UserProfileUpdate(BaseModel):
    """User profile update model"""
    name: Optional[str] = None
    diet_type: Optional[str] = None
    fitness_goal: Optional[str] = None
    cuisine_preferences: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    health_conditions: Optional[List[str]] = None
    calorie_goal: Optional[int] = None
    budget_preference: Optional[Dict[str, Any]] = None
    cooking_time_preference: Optional[str] = None
    skill_level: Optional[str] = None


class GroceryItemAdd(BaseModel):
    """Add grocery item model"""
    item_name: str = Field(..., description="Name of the grocery item")
    quantity: float = Field(1.0, description="Quantity")
    unit: str = Field("pieces", description="Unit (kg, g, pieces, etc.)")
    category: Optional[str] = Field(None, description="Category")
    is_perishable: bool = Field(False, description="Whether item is perishable")
    days_until_expiry: Optional[int] = Field(None, description="Days until expiry")


class GroceryItemRemove(BaseModel):
    """Remove grocery item model"""
    item_name: str = Field(..., description="Name of the grocery item to remove")


class MealPlanSave(BaseModel):
    """Save meal plan model"""
    plan_date: str = Field(..., description="Date in YYYY-MM-DD format")
    meal_type: str = Field(..., description="breakfast/lunch/dinner/snack")
    recipe_name: str = Field(..., description="Name of the recipe")
    calories: int = Field(0, description="Calories")
    protein_g: float = Field(0, description="Protein in grams")
    carbs_g: float = Field(0, description="Carbs in grams")
    fat_g: float = Field(0, description="Fat in grams")
    notes: Optional[str] = Field(None, description="Additional notes")


class RecipeRating(BaseModel):
    """Recipe rating model"""
    recipe_name: str = Field(..., description="Name of the recipe")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback: Optional[str] = Field(None, description="Optional feedback text")
    cuisine: Optional[str] = Field(None, description="Cuisine type")
    recipe_content: Optional[str] = Field(None, description="Full recipe content")


class APIResponse(BaseModel):
    """Standard API response model"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


# ============================================================================
# FastAPI App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown"""
    global services
    
    # Startup - Initialize services
    print("🚀 Starting NutriBot Backend API...")
    services = await init_services()
    print("✅ Services initialized")
    
    yield
    
    # Shutdown - Cleanup
    print("🛑 Shutting down NutriBot Backend...")
    if services.get("db"):
        services["db"].conn.close()


app = FastAPI(
    title="NutriBot API",
    description="Smart Meal Assistant Backend API for Android App",
    version="5.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for Android app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services dictionary
services = {}


# ============================================================================
# Service Initialization
# ============================================================================

async def init_services():
    """Initialize all backend services"""
    from groq import Groq
    from database.grocery_db import GroceryDatabase
    from database.feedback_db import FeedbackDatabase
    from tools.tools import load_recipe_dataset, build_recipe_knowledge_base
    from agents.user_profile import UserProfileDB
    from agents.pantry_agent import PantryAgent
    from agents.cooking_agent import CookingAgent
    from agents.memory_agent import MemoryAgent
    from services.price_service import PriceService
    
    # Groq client
    groq_key = os.getenv("GROQ_API_KEY", "")
    client = Groq(api_key=groq_key) if groq_key else None
    
    # Databases
    db = GroceryDatabase(db_path="data/grocery_inventory.db")
    profile_db = UserProfileDB(db_path="data/user_profile.db")
    feedback_db = FeedbackDatabase(db_path="data/feedback.db")
    
    # Recipe knowledge base
    dataset = load_recipe_dataset()
    recipe_kb = build_recipe_knowledge_base(dataset)
    
    # Price service
    price_service = PriceService()
    
    # Agents
    pantry_agent = PantryAgent()
    cooking_agent = CookingAgent()
    memory_agent = MemoryAgent()
    
    return {
        "client": client,
        "db": db,
        "recipe_kb": recipe_kb,
        "profile_db": profile_db,
        "feedback_db": feedback_db,
        "price_service": price_service,
        "pantry_agent": pantry_agent,
        "cooking_agent": cooking_agent,
        "memory_agent": memory_agent,
    }


def get_session_id(user_id: str = None, session_id: str = None) -> str:
    """Get or create session ID"""
    if session_id:
        return session_id
    if user_id:
        return f"{user_id}_{datetime.now().strftime('%Y%m%d')}"
    return str(uuid.uuid4())


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get("/", response_model=APIResponse, tags=["System"])
async def root():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        message="NutriBot API is running",
        data={
            "version": "5.0.0",
            "status": "healthy",
            "groq_available": bool(services.get("client")),
        }
    )


@app.get("/health", tags=["System"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "groq": bool(services.get("client")),
            "database": bool(services.get("db")),
            "profile_db": bool(services.get("profile_db")),
        }
    }


# ============================================================================
# Chat/Conversation Endpoints
# ============================================================================

@app.post("/chat", response_model=APIResponse, tags=["Chat"])
async def chat(message: UserMessage):
    """
    Send a message to NutriBot and get a response.
    
    Supports:
    - Recipe generation
    - Pantry management
    - Nutrition tracking
    - Meal planning
    - Health advice
    - Budget analysis
    """
    from agents.streaming_pipeline import run_streaming_pipeline
    from agents.workflow import build_initial_state
    
    session_id = get_session_id(message.user_id, message.session_id)
    
    # Build initial state
    state = build_initial_state(
        user_query=message.query,
        dietary_restrictions=message.dietary_restrictions or [],
        health_conditions=message.health_conditions or [],
        calorie_limit=message.calorie_limit or 500,
        budget_limit=message.budget_limit or 500.0,
        servings=message.servings or 2,
        cuisine_preference=message.cuisine_preference or "Indian",
        extra_ingredients=[],
        conversation_history=[],
    )
    state["session_id"] = session_id
    state["user_id"] = message.user_id
    state["input_mode"] = message.input_mode
    
    # Run pipeline (non-streaming for API)
    final_state = None
    assistant_message = ""
    intent = "general"
    nutrition_data = None
    budget_data = None
    eco_data = None
    generated_recipe = None
    
    for event in run_streaming_pipeline(
        state,
        services["client"],
        services["db"],
        services["recipe_kb"],
        profile_db=services["profile_db"],
        feedback_db=services["feedback_db"],
    ):
        if event.get("type") == "complete":
            final_state = event.get("state", {})
    
    if final_state:
        assistant_message = (
            final_state.get("assistant_message") or
            final_state.get("generated_recipe") or
            "I processed your request."
        )
        intent = final_state.get("intent", "general")
        nutrition_data = final_state.get("nutrition_data")
        budget_data = final_state.get("budget_analysis")
        eco_data = final_state.get("eco_score")
        generated_recipe = final_state.get("generated_recipe")
    
    return APIResponse(
        success=True,
        message="Chat processed successfully",
        data={
            "response": assistant_message,
            "intent": intent,
            "session_id": session_id,
            "nutrition": nutrition_data,
            "budget": budget_data,
            "eco": eco_data,
            "generated_recipe": generated_recipe,
        }
    )


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(message: UserMessage):
    """
    Stream chat response as Server-Sent Events.
    Use this for real-time responses in Android app.
    """
    from agents.streaming_pipeline import run_streaming_pipeline
    from agents.workflow import build_initial_state
    
    async def generate():
        session_id = get_session_id(message.user_id, message.session_id)
        
        state = build_initial_state(
            user_query=message.query,
            dietary_restrictions=message.dietary_restrictions or [],
            health_conditions=message.health_conditions or [],
            calorie_limit=message.calorie_limit or 500,
            budget_limit=message.budget_limit or 500.0,
            servings=message.servings or 2,
            cuisine_preference=message.cuisine_preference or "Indian",
            extra_ingredients=[],
            conversation_history=[],
        )
        state["session_id"] = session_id
        state["user_id"] = message.user_id
        
        for event in run_streaming_pipeline(
            state,
            services["client"],
            services["db"],
            services["recipe_kb"],
            profile_db=services["profile_db"],
            feedback_db=services["feedback_db"],
        ):
            import json
            yield f"data: {json.dumps(event)}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================================
# User Profile Endpoints
# ============================================================================

@app.get("/profile/{user_id}", response_model=APIResponse, tags=["Profile"])
async def get_profile(user_id: str):
    """Get user profile"""
    profile = services["profile_db"].get_full_profile()
    
    # Add user_id to profile
    profile["user_id"] = user_id
    
    return APIResponse(
        success=True,
        message="Profile retrieved",
        data=profile
    )


@app.put("/profile/{user_id}", response_model=APIResponse, tags=["Profile"])
async def update_profile(user_id: str, profile_update: UserProfileUpdate):
    """Update user profile"""
    profile_db = services["profile_db"]
    
    # Update each field
    update_dict = profile_update.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        profile_db.set(key, value)
    
    # Get updated profile
    updated_profile = profile_db.get_full_profile()
    updated_profile["user_id"] = user_id
    
    return APIResponse(
        success=True,
        message="Profile updated successfully",
        data=updated_profile
    )


@app.delete("/profile/{user_id}", response_model=APIResponse, tags=["Profile"])
async def reset_profile(user_id: str):
    """Reset user profile"""
    services["profile_db"].clear()
    
    return APIResponse(
        success=True,
        message="Profile reset successfully",
        data={"user_id": user_id}
    )


# ============================================================================
# Pantry/Grocery Endpoints
# ============================================================================

@app.get("/pantry", response_model=APIResponse, tags=["Pantry"])
async def get_pantry(user_id: Optional[str] = None):
    """Get all pantry items"""
    groceries = services["db"].get_all_groceries()
    
    return APIResponse(
        success=True,
        message="Pantry retrieved",
        data={
            "items": groceries,
            "count": len(groceries),
            "expiring_soon": services["db"].get_expiring_soon(3)
        }
    )


@app.post("/pantry", response_model=APIResponse, tags=["Pantry"])
async def add_to_pantry(item: GroceryItemAdd):
    """Add item to pantry"""
    success = services["db"].add_grocery(
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        category=item.category,
        is_perishable=item.is_perishable,
        days_until_expiry=item.days_until_expiry,
    )
    
    if success:
        return APIResponse(
            success=True,
            message=f"Added {item.quantity} {item.unit} {item.item_name} to pantry",
            data={"item": item.model_dump()}
        )
    else:
        return APIResponse(
            success=False,
            message="Failed to add item",
            error="Database error"
        )


@app.delete("/pantry", response_model=APIResponse, tags=["Pantry"])
async def remove_from_pantry(item: GroceryItemRemove):
    """Remove item from pantry"""
    success = services["db"].delete_grocery(item.item_name)
    
    if success:
        return APIResponse(
            success=True,
            message=f"Removed {item.item_name} from pantry",
            data={"removed_item": item.item_name}
        )
    else:
        return APIResponse(
            success=False,
            message=f"Item {item.item_name} not found in pantry",
            error="Not found"
        )


@app.delete("/pantry/all", response_model=APIResponse, tags=["Pantry"])
async def clear_pantry():
    """Clear all pantry items"""
    services["db"].clear_inventory()
    
    return APIResponse(
        success=True,
        message="Pantry cleared successfully",
        data={}
    )


@app.get("/pantry/expiring", response_model=APIResponse, tags=["Pantry"])
async def get_expiring_items(days: int = 3):
    """Get items expiring within days"""
    expiring = services["db"].get_expiring_soon(days)
    
    return APIResponse(
        success=True,
        message=f"Items expiring within {days} days",
        data={
            "items": expiring,
            "count": len(expiring),
            "days": days
        }
    )


# ============================================================================
# Recipe Endpoints
# ============================================================================

@app.post("/recipe/generate", response_model=APIResponse, tags=["Recipes"])
async def generate_recipe(message: UserMessage):
    """
    Generate a recipe based on user query and preferences.
    """
    from agents.receipe_agent import RecipeAgent
    
    # Build state
    from agents.workflow import build_initial_state
    state = build_initial_state(
        user_query=message.query,
        dietary_restrictions=message.dietary_restrictions or [],
        health_conditions=message.health_conditions or [],
        calorie_limit=message.calorie_limit or 500,
        budget_limit=message.budget_limit or 500.0,
        servings=message.servings or 2,
        cuisine_preference=message.cuisine_preference or "Indian",
        extra_ingredients=[],
        conversation_history=[],
    )
    
    # Add pantry items
    state["available_ingredients"] = [
        g["item_name"] for g in services["db"].get_all_groceries()
    ]
    
    # Generate recipe
    recipe_agent = RecipeAgent()
    state = recipe_agent.run(state, client=services["client"])
    
    return APIResponse(
        success=True,
        message="Recipe generated",
        data={
            "recipe": state.get("generated_recipe", ""),
            "ingredients": state.get("recipe_ingredients_structured", []),
            "nutrition": state.get("nutrition_data"),
            "budget": state.get("budget_analysis"),
            "eco_score": state.get("eco_score"),
        }
    )


@app.post("/recipe/rate", response_model=APIResponse, tags=["Recipes"])
async def rate_recipe(rating: RecipeRating):
    """Rate a recipe and provide feedback"""
    recipe_id = services["feedback_db"].save_rating(
        recipe_name=rating.recipe_name,
        rating=rating.rating,
        recipe_content=rating.recipe_content or "",
        feedback_text=rating.feedback or "",
        cuisine=rating.cuisine or "",
    )
    
    return APIResponse(
        success=True,
        message=f"Recipe rated {rating.rating}/5 stars",
        data={
            "recipe_name": rating.recipe_name,
            "rating": rating.rating,
            "recipe_id": recipe_id
        }
    )


# ============================================================================
# Meal Plan Endpoints
# ============================================================================

@app.get("/mealplan", response_model=APIResponse, tags=["Meal Plans"])
async def get_meal_plans(days: int = 7):
    """Get meal plans for the last N days"""
    meals = services["db"].get_meal_plans(days)
    
    return APIResponse(
        success=True,
        message=f"Retrieved {len(meals)} meal plans",
        data={
            "meals": meals,
            "count": len(meals),
            "days": days
        }
    )


@app.get("/mealplan/today", response_model=APIResponse, tags=["Meal Plans"])
async def get_today_meal_plans():
    """Get today's meal plans"""
    meals = services["db"].get_meal_plans_today()
    
    # Group by meal type
    grouped = {}
    for meal in meals:
        meal_type = meal.get("meal_type", "other")
        if meal_type not in grouped:
            grouped[meal_type] = []
        grouped[meal_type].append(meal)
    
    return APIResponse(
        success=True,
        message="Today's meal plans retrieved",
        data={
            "meals": meals,
            "grouped": grouped,
            "count": len(meals),
            "date": date.today().isoformat()
        }
    )


@app.post("/mealplan", response_model=APIResponse, tags=["Meal Plans"])
async def save_meal_plan(meal: MealPlanSave):
    """Save a meal plan entry"""
    services["db"].save_meal_plan(
        plan_date=meal.plan_date,
        meal_type=meal.meal_type,
        recipe_name=meal.recipe_name,
        calories=meal.calories,
        protein_g=meal.protein_g,
        carbs_g=meal.carbs_g,
        fat_g=meal.fat_g,
        notes=meal.notes or "",
    )
    
    return APIResponse(
        success=True,
        message=f"Saved {meal.meal_type} meal for {meal.plan_date}",
        data=meal.model_dump()
    )


@app.post("/mealplan/week", response_model=APIResponse, tags=["Meal Plans"])
async def generate_weekly_plan(message: UserMessage):
    """Generate a weekly meal plan"""
    from agents.planner_agent import meal_plan_agent
    from agents.workflow import build_initial_state
    
    state = build_initial_state(
        user_query=message.query,
        dietary_restrictions=message.dietary_restrictions or [],
        health_conditions=message.health_conditions or [],
        calorie_limit=message.calorie_limit or 500,
        budget_limit=message.budget_limit or 500.0,
        servings=message.servings or 2,
        cuisine_preference=message.cuisine_preference or "Indian",
        extra_ingredients=[],
        conversation_history=[],
    )
    
    state["user_profile"] = services["profile_db"].get_full_profile()
    
    state = meal_plan_agent(state, client=services["client"], db=services["db"])
    
    return APIResponse(
        success=True,
        message="Weekly meal plan generated",
        data={
            "plan": state.get("assistant_message", ""),
        }
    )


# ============================================================================
# Nutrition Tracking Endpoints
# ============================================================================

@app.get("/nutrition/today", response_model=APIResponse, tags=["Nutrition"])
async def get_today_nutrition():
    """Get today's nutrition summary"""
    from agents.nutrition_tracker import get_daily_nutrition_summary
    
    # Create dummy state
    from agents.workflow import build_initial_state
    state = build_initial_state(user_query="")
    state["user_profile"] = services["profile_db"].get_full_profile()
    
    state = get_daily_nutrition_summary(state, services["db"], services["client"])
    
    return APIResponse(
        success=True,
        message="Today's nutrition summary",
        data={
            "summary": state.get("daily_nutrition_summary", {}),
            "message": state.get("assistant_message", ""),
            "date": date.today().isoformat()
        }
    )


@app.get("/nutrition/week", response_model=APIResponse, tags=["Nutrition"])
async def get_weekly_nutrition():
    """Get weekly nutrition summary"""
    meals = services["db"].get_meal_plans(7)
    
    # Aggregate by day
    daily_totals = {}
    for meal in meals:
        day = meal.get("plan_date", "")
        if day not in daily_totals:
            daily_totals[day] = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        
        daily_totals[day]["calories"] += meal.get("calories", 0)
        daily_totals[day]["protein_g"] += meal.get("protein_g", 0)
        daily_totals[day]["carbs_g"] += meal.get("carbs_g", 0)
        daily_totals[day]["fat_g"] += meal.get("fat_g", 0)
    
    return APIResponse(
        success=True,
        message="Weekly nutrition summary",
        data={
            "daily_totals": daily_totals,
            "meals": meals,
            "total_calories": sum(m.get("calories", 0) for m in meals)
        }
    )


# ============================================================================
# Budget & Pricing Endpoints
# ============================================================================

@app.get("/budget/cheapest-protein", response_model=APIResponse, tags=["Budget"])
async def get_cheapest_protein(diet_type: str = "vegetarian"):
    """Get cheapest protein source"""
    cheapest = services["price_service"].get_cheapest_protein(diet_type)
    
    return APIResponse(
        success=True,
        message="Cheapest protein source found",
        data=cheapest
    )


@app.get("/budget/prices", response_model=APIResponse, tags=["Budget"])
async def get_all_prices():
    """Get all ingredient prices"""
    prices = services["price_service"].get_all_prices()
    
    return APIResponse(
        success=True,
        message="Retrieved all prices",
        data={"prices": prices, "count": len(prices)}
    )


@app.get("/budget/price/{ingredient}", response_model=APIResponse, tags=["Budget"])
async def get_ingredient_price(ingredient: str, quantity_kg: float = 1.0):
    """Get price for a specific ingredient"""
    price = services["price_service"].get_price(ingredient, quantity_kg)
    
    return APIResponse(
        success=True,
        message=f"Price for {ingredient}",
        data={
            "ingredient": ingredient,
            "price_inr": price,
            "quantity_kg": quantity_kg
        }
    )


@app.post("/budget/price", response_model=APIResponse, tags=["Budget"])
async def update_ingredient_price(ingredient: str, price: float, source: str = "api"):
    """Update ingredient price"""
    services["price_service"].update_price(ingredient, price, source)
    
    return APIResponse(
        success=True,
        message=f"Updated price for {ingredient} to ₹{price}",
        data={"ingredient": ingredient, "price": price}
    )


# ============================================================================
# Image/Vision Endpoints
# ============================================================================

@app.post("/vision/analyze", response_model=APIResponse, tags=["Vision"])
async def analyze_image(
    file: UploadFile = File(...),
    context: str = Form("fridge"),
    user_id: Optional[str] = Form(None)
):
    """Analyze food image and detect ingredients"""
    from vision.vision_agent import analyse_food_image, image_to_inventory
    
    # Read image bytes
    image_bytes = await file.read()
    
    # Analyze image
    if services["client"]:
        result = analyse_food_image(image_bytes, services["client"], context)
    else:
        from vision.vision_agent import analyse_food_image_anthropic
        result = analyse_food_image_anthropic(image_bytes, context)
    
    # Optionally add to inventory
    if result.get("detected_items") and user_id:
        summary = image_to_inventory(image_bytes, services["db"], services["client"], context)
        result["inventory_summary"] = summary[1]
    
    return APIResponse(
        success=True,
        message="Image analyzed",
        data=result
    )


# ============================================================================
# Voice Endpoints
# ============================================================================

@app.post("/voice/transcribe", response_model=APIResponse, tags=["Voice"])
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en")
):
    """Transcribe audio to text using Groq Whisper"""
    from voice.voice_agent import transcribe_audio_groq
    
    audio_bytes = await file.read()
    text = transcribe_audio_groq(audio_bytes, services["client"], file.filename)
    
    return APIResponse(
        success=True,
        message="Audio transcribed",
        data={
            "text": text,
            "language": language
        }
    )


# ============================================================================
# Shopping List Endpoints
# ============================================================================

@app.post("/shopping/generate", response_model=APIResponse, tags=["Shopping"])
async def generate_shopping_list(message: UserMessage):
    """Generate shopping list based on user request"""
    from agents.shopping_agent import shopping_agent
    from agents.workflow import build_initial_state
    
    state = build_initial_state(
        user_query=message.query,
        dietary_restrictions=message.dietary_restrictions or [],
        health_conditions=message.health_conditions or [],
        calorie_limit=message.calorie_limit or 500,
        budget_limit=message.budget_limit or 500.0,
        servings=message.servings or 2,
        cuisine_preference=message.cuisine_preference or "Indian",
        extra_ingredients=[],
        conversation_history=[],
    )
    
    state["user_profile"] = services["profile_db"].get_full_profile()
    state["recipe_ingredients_structured"] = []
    
    state = shopping_agent(state, db=services["db"], client=services["client"])
    
    return APIResponse(
        success=True,
        message="Shopping list generated",
        data={
            "shopping_list": state.get("assistant_message", ""),
        }
    )


# ============================================================================
# Cooking Mode Endpoints
# ============================================================================

@app.post("/cooking/parse", response_model=APIResponse, tags=["Cooking"])
async def parse_recipe_steps(recipe_text: str):
    """Parse recipe into step-by-step instructions"""
    from agents.cooking_agent import CookingAgent
    
    cooking_agent = CookingAgent()
    steps = cooking_agent.parse_recipe_steps(recipe_text)
    
    return APIResponse(
        success=True,
        message=f"Parsed {len(steps)} steps",
        data={
            "steps": steps,
            "total_steps": len(steps)
        }
    )


@app.get("/cooking/step/{recipe_id}/{step_index}", response_model=APIResponse, tags=["Cooking"])
async def get_cooking_step(recipe_id: str, step_index: int):
    """Get a specific cooking step"""
    # Store recipes in session or database
    # For now, return error if no recipe found
    return APIResponse(
        success=False,
        message="Recipe not found in session",
        error="No recipe stored for this session"
    )


# ============================================================================
# Eco Score Endpoints
# ============================================================================

@app.post("/eco/calculate", response_model=APIResponse, tags=["Eco"])
async def calculate_eco_score(ingredients: List[Dict[str, Any]]):
    """Calculate eco score for ingredients"""
    from agents.eco_agent import eco_agent
    from agents.workflow import build_initial_state
    
    state = build_initial_state(user_query="")
    state["recipe_ingredients_structured"] = ingredients
    state["user_profile"] = services["profile_db"].get_full_profile()
    
    state = eco_agent(state, db=services["db"])
    
    return APIResponse(
        success=True,
        message="Eco score calculated",
        data=state.get("eco_score", {})
    )


# ============================================================================
# Health Advice Endpoints
# ============================================================================

@app.post("/health/advice", response_model=APIResponse, tags=["Health"])
async def get_health_advice(message: UserMessage):
    """Get personalized health advice"""
    from agents.health_agent import health_agent
    from agents.workflow import build_initial_state
    
    state = build_initial_state(
        user_query=message.query,
        dietary_restrictions=message.dietary_restrictions or [],
        health_conditions=message.health_conditions or [],
        calorie_limit=message.calorie_limit or 500,
        budget_limit=message.budget_limit or 500.0,
        servings=message.servings or 2,
        cuisine_preference=message.cuisine_preference or "Indian",
        extra_ingredients=[],
        conversation_history=[],
    )
    
    state["user_profile"] = services["profile_db"].get_full_profile()
    state["intent"] = "health_advice"
    
    state = health_agent(state, client=services["client"])
    
    return APIResponse(
        success=True,
        message="Health advice generated",
        data={
            "advice": state.get("assistant_message", ""),
            "recommendations": state.get("health_recommendations", "")
        }
    )


# ============================================================================
# Feedback & Analytics Endpoints
# ============================================================================

@app.get("/feedback/stats", response_model=APIResponse, tags=["Feedback"])
async def get_feedback_stats():
    """Get feedback statistics"""
    stats = services["feedback_db"].get_preference_summary()
    
    return APIResponse(
        success=True,
        message="Feedback statistics",
        data=stats
    )


@app.get("/feedback/top-cuisines", response_model=APIResponse, tags=["Feedback"])
async def get_top_cuisines(min_ratings: int = 1):
    """Get top-rated cuisines"""
    top = services["feedback_db"].get_top_cuisines(min_ratings)
    
    return APIResponse(
        success=True,
        message="Top cuisines retrieved",
        data={"cuisines": top}
    )


@app.get("/feedback/liked-ingredients", response_model=APIResponse, tags=["Feedback"])
async def get_liked_ingredients(min_likes: int = 2):
    """Get most liked ingredients"""
    liked = services["feedback_db"].get_liked_ingredients(min_likes)
    
    return APIResponse(
        success=True,
        message="Liked ingredients retrieved",
        data={"ingredients": liked}
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )