"""
Gemini Pro 2 integration utilities for enhanced AI capabilities.
"""
import os
import asyncio
from rich.console import Console

# Create console instance for pretty printing
console = Console()

# Try to import Google AI modules
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    console.print("[green]Google GenerativeAI imported successfully.[/green]")
except ImportError:
    GEMINI_AVAILABLE = False
    console.print("[yellow]Google GenerativeAI not available. Gemini features will be disabled.[/yellow]")

def initialize_gemini():
    """Initialize the Gemini API with API key from environment."""
    if not GEMINI_AVAILABLE:
        console.print("[yellow]Gemini API not available. Skipping initialization.[/yellow]")
        return False
    try:
        # Try to get API key from environment variables
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            console.print("[yellow]GEMINI_API_KEY not found in environment variables.[/yellow]")
            return False
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        console.print("[green]Gemini API initialized successfully.[/green]")
        return True
    except Exception as e:
        console.print(f"[bold red]Error initializing Gemini API: {e}[/bold red]")
        return False

async def generate_gemini_content(prompt, model="gemini-pro-2", temperature=0.7):
    """Generate content using Gemini models."""
    if not GEMINI_AVAILABLE:
        return "Gemini API not available."
    try:
        # Initialize the model
        model = genai.GenerativeModel(model)
        # Generate content
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"temperature": temperature}
        )
        # Return response
        if hasattr(response, 'text'):
            return response.text
        else:
            return str(response)
    except Exception as e:
        console.print(f"[bold red]Error generating content with Gemini: {e}[/bold red]")
        return f"Error generating content: {str(e)}"

async def get_sound_recommendations(scene_description):
    """Use Gemini to recommend appropriate sound effects for a scene."""
    if not GEMINI_AVAILABLE:
        return "Gemini API not available."
    prompt = f"""
    You are a sound designer for a dark fantasy RPG.
    Based on the following scene description, recommend appropriate sound effects.

    Return a JSON structure with three categories:
    1. ambience - background ambient sounds
    2. effects - one-off sound effects for specific actions or moments
    3. music - mood-appropriate music for the scene

    For each category, provide 2-3 specific suggestions that match the scene's atmosphere.

    Scene description:
    {scene_description}
    """
    response = await generate_gemini_content(prompt, temperature=0.2)
    return response

async def analyze_dice_strategy(dice_notation, context=""):
    """Use Gemini to analyze dice probabilities and suggest strategies."""
    if not GEMINI_AVAILABLE:
        return "Gemini API not available."
    prompt = f"""
    You are a statistical analyst for tabletop RPGs.
    Analyze the following dice roll: {dice_notation}

    Additional context: {context}

    Provide:
    1. Probability distribution summary
    2. Average expected result
    3. Chance of getting specific outcomes (critical success/failure)
    4. Tactical advice based on these probabilities

    Present this information in a concise, easy-to-understand format.
    """
    response = await generate_gemini_content(prompt, temperature=0.1)
    return response

def is_gemini_available():
    """Check if Gemini API is available and initialized."""
    return GEMINI_AVAILABLE
