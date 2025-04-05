#!/usr/bin/env python
"""
RPG Game Master Web Server - Flask-based web interface for the RPG Game Weaver.
Provides real-time interaction with a game master agent through text and voice.
"""
import os
import time
import threading
import asyncio
import queue
import re
import random
import sys
import json
import io # Moved standard imports to top
import wave
import base64

from flask import Flask, render_template, request # Grouped third-party imports
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from openai import OpenAI

# Try to import numpy and sounddevice, but provide fallbacks if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    print("Warning: numpy not available. Audio functionality will be limited.")
    NUMPY_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    print("Warning: sounddevice not available. Audio functionality will be limited.")
    SOUNDDEVICE_AVAILABLE = False

# --- Agents SDK Imports ---
from agents import (
    Agent,
    function_tool,
    trace
)
from agents.voice import (
    StreamedAudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
    VoicePipelineConfig,
    TTSModelSettings
)
# --- End Agents SDK Imports ---

# Import from our utils
from utils import file_utils, db_utils

# Initialize and configure Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'morborg-gamemaster-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Rich console for logging
console = Console()

# Load environment variables
load_dotenv()

# Initialize OpenAI client
try:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        console.print("[bold red]Error: OPENAI_API_KEY not found in .env file.[/bold red]")
        sys.exit(1)
    openai_client = OpenAI(api_key=openai_api_key)  # Ensure OpenAI client is initialized correctly
    # Test connection to OpenAI
    openai_client.models.list()
    console.print("[green]OpenAI client initialized.[/green]")
except Exception as e:
    console.print(f"[bold red]Failed to initialize OpenAI client: {e}[/bold red]")
    sys.exit(1)

# Initialize database
try:
    game_db = db_utils.GameDatabase()
except Exception as e:
    console.print(f"[bold red]Failed to initialize database: {e}[/bold red]")
    sys.exit(1)

# Global variables
GAME_STATE = {
    "world_map": None,
    "local_areas": {}, # Store data for different rooms/areas
    "battle_state": None, # Store current battle info
    "quests": [],
    "players": [],
    "current_location": None, # Track current local area name
    "in_battle": False
}
CURRENT_GAME_FILE = None
AUDIO_RUNNING = False
AUDIO_TASK = None
WEB_CLIENTS = set()  # Track connected web clients
MAP_DATA = { # Keep this separate for potential Gemini generation cache
    "world_map": None,
    "local_areas": {},
    "battle_maps": {}
}
QUEST_DATA = [] # Keep this separate for potential Gemini generation cache
ITEM_DATABASE = [] # Keep this separate for potential Gemini generation cache
MONSTER_DATABASE = [] # Keep this separate for potential Gemini generation cache

# --- Agent Tools, Agent, and Pipeline Setup ---

# Try to import d20 for more advanced dice rolling, with fallback to simple implementation
try:
    import d20
    D20_AVAILABLE = True
except ImportError:
    D20_AVAILABLE = False
    console.print("[yellow]d20 library not available. Using basic dice rolling implementation.[/yellow]")

# --- Helper Functions for Game Data (Moved Before Agent Definition) ---
def generate_monster_database():
    """Generate a basic monster database for the game."""
    global MONSTER_DATABASE
    MONSTER_DATABASE = [
        {
            "name": "Skeleton Warrior", "str": 12, "agi": 10, "pre": 6, "tou": 8, "hp": 20, "ac": 14,
            "attacks": ["Rusted Sword (1d6)", "Bone Claw (1d4)"],
            "special": "Undead: Immune to poison and disease. Takes half damage from piercing weapons.",
            "description": "A grinning skeleton clad in rusted armor..."
        },
        {
            "name": "Dark Cultist", "str": 10, "agi": 12, "pre": 14, "tou": 10, "hp": 18, "ac": 12,
            "attacks": ["Ritual Dagger (1d4+2)", "Dark Incantation (1d8, 30ft range)"],
            "special": "Sacrificial Rite: Can sacrifice 2 HP to add +2 to any roll.",
            "description": "A robed figure with ritual scars..."
        }
    ]
    console.print("[cyan]Generated default monster database.[/cyan]")

def generate_item_database():
    """Generate a basic item database for the game."""
    global ITEM_DATABASE
    ITEM_DATABASE = [
        {
            "name": "Hexblade", "type": "weapon", "value": 120,
            "properties": "Longsword (1d8). On crit, target Presence save or cursed (-2 rolls) 1d4 turns.",
            "description": "A wicked blade with shifting runes..."
        },
        {
            "name": "Scroll of Unmaking", "type": "scroll", "value": 200,
            "properties": "One-time use. Target non-magical object up to door size is disintegrated.",
            "description": "A yellowed parchment, script hurts eyes..."
        }
    ]
    console.print("[cyan]Generated default item database.[/cyan]")

# Ensure databases are populated on server start
generate_monster_database()
generate_item_database()

@function_tool
def lookup_monster(monster_name: str) -> str:
    """Look up a monster in the monster database by name."""
    if not MONSTER_DATABASE: generate_monster_database()
    for monster in MONSTER_DATABASE:
        if monster["name"].lower() == monster_name.lower():
            return json.dumps(monster, indent=2) # Return JSON for potential parsing
    return f"Monster '{monster_name}' not found."

@function_tool
def lookup_item(item_name: str) -> str:
    """Look up an item in the item database by name."""
    if not ITEM_DATABASE: generate_item_database()
    for item in ITEM_DATABASE:
        if item["name"].lower() == item_name.lower():
            return json.dumps(item, indent=2) # Return JSON
    return f"Item '{item_name}' not found."
# --- End Helper Functions ---

@function_tool
def roll_dice_tool(dice_notation: str) -> str:
    """
    Rolls dice based on standard notation (e.g., 'd20', '2d6', '3d8+2') and returns the result as a string.
    Supports advanced notation if d20 library is available, including 4d6kh3 (keep highest 3 of 4d6),
    2d20kl1 (keep lowest 1, advantage), etc.
    """
    if D20_AVAILABLE:
        try:
            # Parse and roll the dice using d20 library
            result = d20.roll(dice_notation)

            # Format the response
            roll_str = str(result)
            total = result.total

            # Add emoji for critical successes/failures on d20
            if dice_notation.lower().strip() == 'd20' and total == 20:
                roll_str += " ✨ Critical Success! ✨"
            elif dice_notation.lower().strip() == 'd20' and total == 1:
                roll_str += " 💀 Critical Failure! 💀"

            result_text = f"Rolling {dice_notation}. Result: {roll_str}. Total: {total}"
            console.print(f"[bold cyan]Dice Roll (d20 lib): {result_text}[/bold cyan]")
            return result_text

        except d20.errors.RollSyntaxError:
            console.print(f"[yellow]Invalid dice notation with d20 lib: '{dice_notation}'. Falling back to basic parser.[/yellow]")
            # Fall back to regex method if the d20 library can't parse it
        except Exception as e:
            console.print(f"[yellow]Error with d20 dice rolling: {e}. Falling back to basic parser.[/yellow]")

    # Basic implementation using regex (fallback or if d20 not available)
    try:
        match = re.match(r'(\d+)?d(\d+)([+-]\d+)?', dice_notation.strip())
        if not match:
            return "Invalid dice notation. Use format like 'd20', '2d6', or '3d8+2'."

        num_dice = int(match.group(1)) if match.group(1) else 1
        dice_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        rolls = [random.randint(1, dice_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier

        roll_details = f"Rolling {num_dice}d{dice_size}"
        if modifier:
            roll_details += f"{'+' if modifier > 0 else ''}{modifier}"

        roll_results = f"Rolls: {rolls} = {sum(rolls)}"
        if modifier:
            roll_results += f" {'+' if modifier > 0 else ''} {modifier} = {total}"

        # Add emoji for critical successes/failures on d20
        if num_dice == 1 and dice_size == 20:
            if rolls[0] == 20:
                roll_results += " ✨ Critical Success! ✨"
            elif rolls[0] == 1:
                roll_results += " 💀 Critical Failure! 💀"

        result = f"{roll_details}. Result: {roll_results}. Total: {total}"
        console.print(f"[bold cyan]Dice Roll (Basic): {result}[/bold cyan]")
        return result
    except Exception as e:
        console.print(f"[bold red]Error in dice rolling: {e}[/bold red]")
        return f"Error rolling dice: {str(e)}"

def get_system_prompt():
    """Generate the system prompt based on current game state."""
    history = game_db.get_game_history(10)
    history_text = "\n".join([f"{event['type']}: {event['description']}" for event in history])
    game_file_name = GAME_STATE.get('game_file', 'None')
    current_scene_name = GAME_STATE.get('current_scene', 'intro')
    player_names = ', '.join([p.get('character_name', 'Unknown') for p in GAME_STATE.get('players', [])])

    # Get relevant game content (if available)
    game_context = ""
    if CURRENT_GAME_FILE:
        # If we have a game file loaded, include a snippet of it for context
        game_name = CURRENT_GAME_FILE.get("name", "None")

        # If we need to examine the game file for relevant content based on the prompt
        # We'll limit how much we send to avoid overwhelming the API
        if "is_truncated" in CURRENT_GAME_FILE and CURRENT_GAME_FILE["is_truncated"]:
            console.print("[cyan]Using truncated game content for system prompt[/cyan]")
            game_content = CURRENT_GAME_FILE.get("content", "")
        else:
            game_content = CURRENT_GAME_FILE.get("content", "")

        # Limit the game content included in the prompt to a reasonable size
        max_context_length = 1000  # Characters - smaller for the system prompt
        if len(game_content) > max_context_length:
            game_context = f"\nGame file: {game_name} (truncated excerpt)\n{game_content[:max_context_length]}..."
        else:
            game_context = f"\nGame file: {game_name}\n{game_content}"

    return f"""
    You are the Game Master for a Mörk Borg roleplaying game.
    Mörk Borg is a dark fantasy RPG with apocalyptic themes. Maintain a grim, atmospheric, and slightly menacing tone.
    Current game state: Game file: {game_file_name}, Current scene: {current_scene_name},
    Players: {player_names if player_names else 'None'}
    Recent game history: {history_text}
    {game_context}

    Respond as a descriptive, atmospheric game master. Be concise yet vivid.
    Create dramatic and immersive narratives. Call for dice rolls using the 'roll_dice_tool' when appropriate.
    Do not roll dice yourself.
    **Output Format:** Provide only the dialogue or narration directly. Example: `The air grows cold.`
    """

game_master_agent = Agent(
    name="GameMaster",
    instructions=get_system_prompt,
    model="gpt-4o",
    tools=[roll_dice_tool, lookup_monster, lookup_item], # Added lookup tools
)

gm_tts_settings = TTSModelSettings(
    instructions="Personality: dramatic, ominous game master. Tone: Deep, authoritative, slightly menacing. "
                "Tempo: Speak deliberately, with pauses."
)

voice_pipeline_config = VoicePipelineConfig(
    tts_settings=gm_tts_settings,
    trace_include_sensitive_data=False,
    trace_include_sensitive_audio_data=False,
    workflow_name="RPG Game Master Web Session"
)

pipeline = VoicePipeline(
    workflow=SingleAgentVoiceWorkflow(agent=game_master_agent),
    config=voice_pipeline_config
)

# --- End Agent/Pipeline Setup ---

# Create necessary directories
os.makedirs("game_files", exist_ok=True)
os.makedirs("chroma_db", exist_ok=True)

# Flask routes
@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')

@app.route('/session', methods=['GET'])
def get_session_key():
    """Handle session setup (ephemeral key generation removed)."""
    try:
        # TODO: Re-implement ephemeral key generation if needed for WebRTC
        # For now, we assume the client will use the standard API key or another method
        console.print("[yellow]Ephemeral key generation skipped (relying on client-side key).[/yellow]")
        # Return a placeholder or indicate that the client should handle auth
        return {"message": "Server ready, client should handle authentication."}, 200
    except Exception as e:
        console.print(
            f"[bold red]Error during session setup (ephemeral key skipped): {e}[/bold red]"
        )
        return {"error": str(e)}, 500

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    WEB_CLIENTS.add(request.sid)
    emit('system', {'message': 'Connected to RPG Game Master'})
    console.print(f"[green]Web client connected: {request.sid}[/green]")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if request.sid in WEB_CLIENTS:
        WEB_CLIENTS.remove(request.sid)
    console.print(f"[yellow]Web client disconnected: {request.sid}[/yellow]")

@socketio.on('command')
def handle_command(data):
    """Process commands from web clients"""
    command = data.get('command', '').strip()
    voice_settings = data.get('voiceSettings', {})

    if not command:
        emit('response', {'error': True, 'message': 'Empty command'})
        return

    console.print(f"[cyan]Received command: {command}[/cyan]")

    # Process the command
    try:
        response = process_web_command(command, voice_settings)
        if response:
            emit('response', {'error': False, 'message': response})
    except Exception as e:
        console.print(f"[bold red]Error processing command: {e}[/bold red]")
        emit('response', {'error': True, 'message': str(e)})

@socketio.on('get_map_data')
def handle_get_map_data(data):
    """Handle requests for map data from the client."""
    map_type = data.get('type')
    location = data.get('location') # For local maps
    console.print(f"[cyan]Received request for map data: type={map_type}, location={location}[/cyan]")

    map_to_send = None
    if map_type == 'world':
        # Use cached/generated world map data if available
        map_to_send = GAME_STATE.get('world_map', MAP_DATA.get('world_map'))
        if not map_to_send:
             # TODO: Implement Gemini generation if needed and available
             console.print("[yellow]World map data not available.[/yellow]")
             map_to_send = {"name": "The Dying Lands", "description": "Placeholder world map."} # Placeholder
    elif map_type == 'local':
        # Use cached/generated local area data
        map_to_send = GAME_STATE.get('local_areas', {}).get(location, MAP_DATA.get('local_areas', {}).get(location))
        if not map_to_send:
            # TODO: Implement Gemini generation if needed and available
            console.print(f"[yellow]Local map data for '{location}' not available.[/yellow]")
            map_to_send = {"name": location, "description": f"Placeholder description for {location}."} # Placeholder
    else:
        console.print(f"[red]Unknown map type requested: {map_type}[/red]")
        emit('system', {'message': f"Unknown map type: {map_type}", 'isError': True})
        return

    if map_to_send:
        emit('map_data', {'type': map_type, 'map': map_to_send})
    else:
        emit('system', {'message': f"Could not retrieve map data for {map_type} {location or ''}", 'isError': True})


@socketio.on('get_battle_state')
def handle_get_battle_state():
    """Send the current battle state to the client."""
    if GAME_STATE.get('in_battle') and GAME_STATE.get('battle_state'):
        console.print("[cyan]Sending current battle state to client.[/cyan]")
        emit('battle_state_update', GAME_STATE['battle_state'])
    else:
        console.print("[yellow]Request for battle state, but not in battle.[/yellow]")
        emit('system', {'message': 'Not currently in battle.'})

@socketio.on('battle_action')
def handle_battle_action(data):
    """Handle actions performed during battle (targeting, HP updates, etc.)."""
    action = data.get('action')
    target = data.get('target')
    hp = data.get('hp')
    # Add more parameters as needed (e.g., ability used) for battle actions

    console.print(f"[magenta]Received battle action: {action}, Target: {target}, HP: {hp}[/magenta]")

    if not GAME_STATE.get('in_battle') or not GAME_STATE.get('battle_state'):
        emit('system', {'message': 'Cannot perform battle action: Not in battle.', 'isError': True})
        return

    battle_state = GAME_STATE['battle_state']
    updated = False

    if action == 'update_hp' and target and hp is not None:
        for combatant in battle_state.get('combatants', []):
            if combatant.get('name') == target:
                try:
                    combatant['hp'] = int(hp)
                    updated = True
                    console.print(f"Updated HP for {target} to {hp}")
                    break
                except ValueError:
                    console.print(f"[red]Invalid HP value received: {hp}[/red]")
                    emit('system', {'message': f"Invalid HP value: {hp}", 'isError': True})
                    return
        if not updated:
             console.print(f"[yellow]Could not find combatant '{target}' to update HP.[/yellow]")

    elif action == 'target' and target:
        # Update the 'targeted' status in the battle state
        for combatant in battle_state.get('combatants', []):
            combatant['targeted'] = (combatant.get('name') == target)
        updated = True
        console.print(f"Set target to {target}")

    elif action == 'next_turn' and target: # Target here is the combatant whose turn it is now
         # Update whose turn it is
         battle_state['current_turn_index'] = -1 # Reset index
         for i, combatant in enumerate(battle_state.get('combatants', [])):
             if combatant.get('name') == target:
                 battle_state['current_turn_index'] = i
                 combatant['is_active_turn'] = True
             else:
                 combatant['is_active_turn'] = False
         updated = True
         console.print(f"Advanced turn to {target}")

    # Add more actions as needed (e.g., 'use_ability', 'move') for battle actions

    if updated:
        # Store the updated battle state
        GAME_STATE['battle_state'] = battle_state
        # Broadcast the updated state to all clients
        socketio.emit('battle_state_update', battle_state)
        # Optionally save game state immediately after battle update
        # save_game_web()


@socketio.on('add_quest')
def handle_add_quest(data):
    """Add a new quest to the game state."""
    title = data.get('title')
    description = data.get('description')
    objectives = data.get('objectives', [])
    rewards = data.get('rewards', [])

    if not title or not description or not objectives:
        emit('system', {'message': 'Quest requires title, description, and objectives.', 'isError': True})
        return

    new_quest = {
        "id": f"quest_{len(GAME_STATE.get('quests', [])) + 1}",
        "title": title,
        "description": description,
        "objectives": [{"text": obj, "completed": False} for obj in objectives],
        "rewards": rewards,
        "status": "active" # active, completed, failed
    }

    if 'quests' not in GAME_STATE:
        GAME_STATE['quests'] = []

    GAME_STATE['quests'].append(new_quest)
    console.print(f"[green]Added new quest: {title}[/green]")
    # Broadcast the updated quest list (or just the new quest)
    socketio.emit('quest_update', {'quests': GAME_STATE['quests']})
    # Optionally save game state
    # save_game_web()


@socketio.on('voice_toggle')
def handle_voice_toggle(data):
    """Toggle voice processing on/off"""
    global AUDIO_RUNNING

    enabled = data.get('enabled', False)

    if enabled and not AUDIO_RUNNING:
        start_audio_processing_web()
    elif not enabled and AUDIO_RUNNING:
        stop_audio_processing_web()

# Game functions adapted for web interface
def process_web_command(command, voice_settings=None):
    """Process commands from web interface"""
    command = command.lower().strip()

    if command == "help":
        return format_help_for_web()
    if command == "start":
        return start_game_web()
    if command == "players":
        return list_players_web()
    if command == "games":
        return load_game_files_web()
    if command == "voice on":
        start_audio_processing_web()
        return "Attempting to start voice interaction..."
    if command == "voice off":
        stop_audio_processing_web()
        return "Attempting to stop voice interaction..."
    if command == "save":
        return save_game_web()
    if command == "history":
        return show_game_history_web()
    if command.startswith("roll "):
        # Use the agent tool directly for text rolls
        result = roll_dice_tool(command[5:])
        return f"Roll Result: {result}"
    if command.startswith("lookup monster "):
        monster_name = command[15:].strip()
        result = lookup_monster(monster_name)
        # Try parsing JSON for better display, fallback to raw string
        try:
            monster_data = json.loads(result)
            formatted_result = (
                f"Monster: {monster_data['name']}\n"
                f"Stats: STR {monster_data['str']}, AGI {monster_data['agi']}, "
                f"PRE {monster_data['pre']}, TOU {monster_data['tou']}\n"
                f"HP: {monster_data['hp']}, AC: {monster_data['ac']}\n"
                f"Attacks: {', '.join(monster_data['attacks'])}\n"
                f"Special: {monster_data['special']}\n"
                f"Desc: {monster_data['description']}"
            )
            return formatted_result
        except (json.JSONDecodeError, KeyError):
            return result  # Return raw string if JSON parsing fails
    if command.startswith("lookup item "):
        item_name = command[12:].strip()
        result = lookup_item(item_name)
        try:
            item_data = json.loads(result)
            formatted_result = (
                f"Item: {item_data['name']} ({item_data['type']})\n"
                f"Value: {item_data['value']} silver\n"
                f"Properties: {item_data['properties']}\n"
                f"Desc: {item_data['description']}"
            )
            return formatted_result
        except (json.JSONDecodeError, KeyError):
            return result  # Return raw string if JSON parsing fails

    # If not a system command, process as game input (text-based)
    response = generate_game_response(command)

    # Add to game history for tracking
    game_db.add_game_event("player_command", f"Player: {command}\nGM: {response}")

    # Text-based commands generate response. TTS (Text-to-Speech) is handled by the pipeline.
    return response

def format_help_for_web():
    """Format help text for web display"""
    help_text = """
    <strong>Available Commands:</strong>

    <span class="cmd">help</span> - Show this help message
    <span class="cmd">start</span> - Start or resume a game
    <span class="cmd">players</span> - List current players
    <span class="cmd">games</span> - List and select available game files
    <span class="cmd">voice on</span> - Enable speech recognition
    <span class="cmd">voice off</span> - Disable speech recognition
    <span class="cmd">save</span> - Save current game state
    <span class="cmd">history</span> - Show recent game history
    <span class="cmd">roll <dice></span> - Roll dice (e.g., 'roll d20', 'roll 2d6+1')
    <span class="cmd">lookup monster <name></span> - Look up monster stats
    <span class="cmd">lookup item <name></span> - Look up item details
    <span class="cmd">exit</span> or <span class="cmd">quit</span> - Exit the application (terminates server)

    You can also just type what your character is doing or saying.
    """
    return help_text

def load_game_files_web():
    """Load available game files and return formatted list"""
    available_games = file_utils.list_available_games()

    if not available_games:
        return "No game files found in the game_files directory. Please add some .txt or .pdf files."

    games_list = "<strong>Available game files:</strong><br>"
    for i, game_file in enumerate(available_games):
        games_list += f"{i+1}. {os.path.basename(game_file)}<br>"

    games_list += "<br>To select a game, type a number. For example: '1' to select the first game."

    # Set up a listener for game selection
    socketio.on('game_selection')(lambda data: handle_game_selection(data, available_games))

    return games_list

def handle_game_selection(data, available_games):
    """Handle game file selection from web client"""
    selection = data.get('selection', '')
    try:
        selection_int = int(selection)
        if 1 <= selection_int <= len(available_games):
            selected_file = available_games[selection_int - 1]
            console.print(f"[bold green]Loading game file: {os.path.basename(selected_file)}[/bold green]")

            game_content = file_utils.load_game_file(selected_file)
            if game_content is None:
                emit('response', {
                    'error': True,
                    'message': f"Failed to load {os.path.basename(selected_file)}. Please try another."
                })
                return

            # Check if the game content is too large for efficient memory handling
            content_length = len(game_content)
            console.print(f"[cyan]Game file size: {content_length} characters[/cyan]")

            # For large files, we'll create a summarized version to use with audio
            max_content_size = 250000  # 250k characters max for full content

            global CURRENT_GAME_FILE
            if content_length > max_content_size:
                console.print(f"[yellow]Game file is large ({content_length} chars). Creating summary for audio system.[/yellow]")
                # Store full content for searching but use a truncated version for context
                CURRENT_GAME_FILE = {
                    "path": selected_file,
                    "name": os.path.basename(selected_file),
                    "content": game_content[:max_content_size],  # Truncated for system prompts
                    "full_content": game_content,  # Full content available for specific searches
                    "is_truncated": True
                }

                emit('response', {
                    'error': False,
                    'message': f"Game file loaded: {os.path.basename(selected_file)} ({content_length} characters, truncated for audio processing)"
                })
            else:
                CURRENT_GAME_FILE = {
                    "path": selected_file,
                    "name": os.path.basename(selected_file),
                    "content": game_content,
                    "is_truncated": False
                }

                emit('response', {
                    'error': False,
                    'message': f"Game file loaded: {os.path.basename(selected_file)} ({content_length} characters)"
                })
        else:
            emit('response', {'error': True, 'message': "Invalid selection. Please enter a number from the list."})
    except ValueError:
        emit('response', {'error': True, 'message': "Invalid input. Please enter a number."})
    except Exception as e:
        emit('response', {'error': True, 'message': f"An unexpected error occurred: {e}"})

def check_existing_game_web():
    """Check for existing game state in the database for web client"""
    try:
        existing_state = game_db.load_game_state()
        if existing_state:
            return existing_state
        return None
    except Exception as e:
        console.print(f"[bold red]Error checking for existing game state: {e}[/bold red]")
        return None

def start_game_web():
    """Start or resume the game for web client"""
    global GAME_STATE

    # Check if we already have a game state
    if not GAME_STATE:
        # Try to load from database
        GAME_STATE = check_existing_game_web()

        # If still no game state, we need to set up a new game
        # For web, we'll return a message asking for players
        if not GAME_STATE:
            return "No existing game found. Please add players to start a new game."

    # If game state is now available, start the game
    if GAME_STATE:
        # Introductory narration
        intro = generate_game_response("Introduce the game and set the scene for the players.")

        # Add game start event
        game_db.add_game_event("game_started", intro)

        return intro

    return "Failed to start game. Please set up players and a game file."

def list_players_web():
    """Return players info for web client and trigger modal display"""
    if GAME_STATE and "players" in GAME_STATE:
        # Emit an event with the players data for the modal
        socketio.emit('game_state', {'players': GAME_STATE["players"]})
        return "Displaying players..."

    return "No players found. Start a new game to add players."

def save_game_web():
    """Save the current game state for web client"""
    if GAME_STATE:
        game_db.store_game_state(GAME_STATE)

        # Also save to file as backup
        file_utils.save_game_state(GAME_STATE)

        return "Game state saved!"

    return "No game in progress to save."

def show_game_history_web():
    """Show game history for web client"""
    history = game_db.get_game_history(20)

    if history:
        # Emit an event with the history data for the modal
        socketio.emit('history', {'history': history})
        return "Displaying game history..."

    return "No game history found."

def generate_game_response(prompt):
    """Generate a response from the Game Master using OpenAI"""
    # Get recent game history for context
    history = game_db.get_game_history(10)
    history_text = "\n".join([f"{event['type']}: {event['description']}" for event in history])

    # Get relevant game content (if available)
    game_context = ""
    if CURRENT_GAME_FILE:
        # If we have a game file loaded, include a snippet of it for context
        game_name = CURRENT_GAME_FILE.get("name", "None")

        # If we need to examine the game file for relevant content based on the prompt
        # We'll limit how much we send to avoid overwhelming the API
        if "is_truncated" in CURRENT_GAME_FILE and CURRENT_GAME_FILE["is_truncated"]:
            console.print("[cyan]Using truncated game content for response generation[/cyan]")
            game_content = CURRENT_GAME_FILE.get("content", "")
        else:
            game_content = CURRENT_GAME_FILE.get("content", "")

        # Limit the game content included in the prompt to a reasonable size
        max_context_length = 2000  # Characters
        if len(game_content) > max_context_length:
            game_context = f"Game file: {game_name} (Note: Using a small excerpt of the game file due to size)\n\nExcerpt:\n{game_content[:max_context_length]}..."
        else:
            game_context = f"Game file: {game_name}\n\n{game_content}"

    # Create system prompt with game context for OpenAI
    system_prompt = f"""
    You are the Game Master for a Mörk Borg roleplaying game.
    Mörk Borg is a dark fantasy RPG with apocalyptic themes.

    Current game state:
    - Game file: {GAME_STATE.get('game_file', 'None')}
    - Current scene: {GAME_STATE.get('current_scene', 'intro')}
    - Players: {', '.join([p.get('character_name', 'Unknown') for p in GAME_STATE.get('players', [])])}

    Recent game history:
    {history_text}

    {game_context if game_context else ""}

    Respond as a descriptive, atmospheric game master. Be concise yet vivid.
    Create dramatic and immersive narratives. When appropriate, call for dice rolls.

    **Output Format:** Provide only the dialogue or narration directly. Example: `The crypt door creaks open.`
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # Using gpt-4o for potentially better instruction following
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        console.print(f"[bold red]Error generating response: {e}[/bold red]")
        return "The Game Master pauses for a moment, lost in thought..."

# --- New Async Audio Processing for Web Server ---
ASYNC_LOOP = None  # Global asyncio loop

def run_async_loop():
    """Runs the asyncio event loop in a separate thread."""
    global ASYNC_LOOP
    ASYNC_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(ASYNC_LOOP)
    console.print("[cyan]Asyncio event loop started in background thread.[/cyan]")
    ASYNC_LOOP.run_forever()
    console.print("[cyan]Asyncio event loop stopped.[/cyan]")

    # Create a queue for audio data processing
web_audio_queue = queue.Queue()

async def process_audio_queue(input_stream):
    """Process audio data from the queue and feed it to the input stream."""
    # No need for global declaration as we're only reading AUDIO_RUNNING status
    try:
        while AUDIO_RUNNING:
            try:
                # Get audio from the queue with a timeout (non-blocking)
                audio_data = web_audio_queue.get(block=True, timeout=0.1)
                # Feed it to the input stream
                await input_stream.add_audio(audio_data)
                # Mark task as done
                web_audio_queue.task_done()
            except queue.Empty:
                # No audio data in the queue, just wait a bit
                await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        console.print("[yellow]Web audio processing task cancelled.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error in web audio processing task: {e}[/bold red]")

async def run_voice_pipeline_web():
    """Runs the voice pipeline, emitting events via SocketIO."""
    global AUDIO_RUNNING
    AUDIO_RUNNING = True
    console.print("[cyan]Starting web voice pipeline...[/cyan]")
    socketio.emit('system', {'message': 'Voice pipeline starting...'})

    # Audio debugging
    debug_audio = True
    console.print("[yellow]Audio debugging enabled[/yellow]")

    # Force audio context resume in browser for audio processing
    socketio.emit('audio_init', {'message': 'Initialize audio context'})

    input_stream = StreamedAudioInput()

    def audio_callback(indata, _frames, _time, status):
        """Callback function for sounddevice input stream."""
        if status:
            console.print(f"[yellow]Audio Callback Status: {status}[/yellow]")
        if AUDIO_RUNNING:
            # Put the audio in the queue instead of calling the coroutine directly
            web_audio_queue.put(indata.copy())
        # When AUDIO_RUNNING is False, we simply stop adding audio
        # No explicit stream closing needed in the callback

    samplerate = sd.query_devices(kind='input')['default_samplerate']
    stream = sd.InputStream(samplerate=samplerate, channels=1, dtype='int16', callback=audio_callback)

    # Create and track the audio processing task
    processor_task = asyncio.create_task(process_audio_queue(input_stream))

    temp_audio_files = []  # Keep track of temp files to delete

    try:
        stream.start()
        console.print("[green]Microphone stream started (web). Listening...[/green]")
        socketio.emit('system', {'message': 'Listening...'})

        with trace("RPG Game Master Web Voice Turn"):
            result = await pipeline.run(input_stream)

        # Stream audio back to the client(s)
        # This requires sending audio chunks via SocketIO
        async for event in result.stream():
            if not AUDIO_RUNNING:
                break

            if event.type == "voice_stream_event_audio":
                # Convert numpy array to bytes with better browser compatibility
                if NUMPY_AVAILABLE:
                    console.print(
                        f"[cyan]Audio event received, data shape: {event.data.shape}, "
                        f"dtype: {event.data.dtype}[/cyan]"
                    )

                    try:
                        # Make sure it's int16 format as expected by our client
                        if event.data.dtype != np.int16:
                            console.print(f"[yellow]Converting audio from {event.data.dtype} to int16[/yellow]")
                            # Scale and convert to int16
                            if np.issubdtype(event.data.dtype, np.floating):
                                # If float data, scale appropriately (-1.0 to 1.0 -> -32768 to 32767)
                                audio_int16 = (event.data * 32767).astype(np.int16)
                            else:
                                # For other integer types
                                audio_int16 = event.data.astype(np.int16)
                        else:
                            audio_int16 = event.data
                    except Exception as audio_err:
                        console.print(f"[bold red]Error processing audio: {audio_err}[/bold red]")
                        audio_int16 = event.data  # Use original data as fallback
                else:
                    console.print("[yellow]Numpy not available, using raw audio data[/yellow]")
                    audio_int16 = event.data

                # Process and send audio data
                try:
                    # Create a WAV file in memory for better browser compatibility
                    import io
                    import wave
                    import base64

    # Check if we have numpy or need to use raw data for audio processing
                    if NUMPY_AVAILABLE:
                        audio_bytes = audio_int16.tobytes()
                    else:
                        audio_bytes = event.data.tobytes() if hasattr(event.data, 'tobytes') else event.data

                    # Create a WAV file in memory
                    buffer = io.BytesIO()
                    with wave.open(buffer, 'wb') as wav_file:
    # pylint: disable=no-member for wave file writing
                        wav_file.setnchannels(1)  # Mono
                        wav_file.setsampwidth(2)  # 16-bit
                        wav_file.setframerate(22050)  # 22.05kHz
                        wav_file.writeframes(audio_bytes)
    # pylint: enable=no-member after wave file writing

                    # Get the WAV bytes
                    buffer.seek(0)
                    wav_bytes = buffer.read()

                    # Base64 encode for reliable transport through Socket.IO
                    b64_encoded = base64.b64encode(wav_bytes).decode('utf-8')

                    console.print("[cyan]Sending WAV audio to client (base64 encoded)[/cyan]")

                    # Send properly formatted audio to client
                    socketio.emit('audio_chunk', {
                        'audio': b64_encoded,
                        'format': 'wav',
                        'encoding': 'base64'
                    })

    # Debug output to help troubleshoot browser audio issues for audio processing
                    if NUMPY_AVAILABLE:
                        audio_min = np.min(audio_int16)
                        audio_max = np.max(audio_int16)
                        console.print(f"[cyan]Audio range: {audio_min} to {audio_max}[/cyan]")

                except Exception as audio_err:
                    console.print(f"[bold red]Error processing audio for client: {audio_err}[/bold red]")

            elif event.type == "voice_stream_event_lifecycle":
                console.print(f"[grey50]Web Lifecycle Event: {event.lifecycle_event}[/grey50]")
                socketio.emit('lifecycle_event', {'event': event.lifecycle_event})
                if event.lifecycle_event == "turn_ended":
                    # Clean up any temp files created for this turn
                    for f_path in temp_audio_files:
                        try:
                            os.remove(f_path)
                        except OSError:
                            pass
                    temp_audio_files.clear()

            elif event.type == "voice_stream_event_transcription":
                console.print(f"[bold cyan]Player said (web):[/bold cyan] {event.text}")
                socketio.emit('player_speech', {'text': event.text})
                game_db.add_game_event("player_speech_web", f"Player said: {event.text}")

            elif event.type == "voice_stream_event_error":
                console.print(f"[bold red]Web Voice Pipeline Error: {event.error}[/bold red]")
                socketio.emit('system', {'message': f"Error: {event.error}", 'isError': True})
                game_db.add_game_event("pipeline_error_web", f"Error: {event.error}")

    except Exception as e:
        console.print(f"[bold red]Error in run_voice_pipeline_web: {e}[/bold red]")
        socketio.emit('system', {'message': f"Pipeline Error: {e}", 'isError': True})
    finally:
        if stream.active:
            stream.stop()
        stream.close()
        console.print("[cyan]Web microphone stream stopped.[/cyan]")
        socketio.emit('system', {'message': 'Voice pipeline stopped.'})
        AUDIO_RUNNING = False
    # Clean up any remaining temp files after audio processing
        for f_path in temp_audio_files:
            try:
                os.remove(f_path)
            except OSError:
                pass

def start_audio_processing_web():
    """Starts the async voice pipeline task for the web server."""
    global AUDIO_TASK, AUDIO_RUNNING
    if AUDIO_RUNNING:
        console.print("[yellow]Web audio processing is already running.[/yellow]")
        return

    if not ASYNC_LOOP or not ASYNC_LOOP.is_running():
        console.print("[bold red]Asyncio loop not running. Cannot start voice processing.[/bold red]")
        socketio.emit('system', {'message': 'Error: Async loop not running.', 'isError': True})
        return

    # Ensure any previous task is cancelled before starting new audio processing
    if AUDIO_TASK and not AUDIO_TASK.done():
        asyncio.run_coroutine_threadsafe(AUDIO_TASK.cancel(), ASYNC_LOOP)

    # Schedule the coroutine to run on the background loop for audio processing
    AUDIO_TASK = asyncio.run_coroutine_threadsafe(run_voice_pipeline_web(), ASYNC_LOOP)
    console.print("[bold green]Web voice interaction enabled.[/bold green]")
    socketio.emit('system', {'message': 'Voice interaction enabled.'})

def stop_audio_processing_web():
    """Stops the async voice pipeline task for the web server."""
    global AUDIO_RUNNING, AUDIO_TASK, ASYNC_LOOP
    if not AUDIO_RUNNING:
        console.print("[yellow]Web audio processing is not running.[/yellow]")
        return

    AUDIO_RUNNING = False  # Signal the loop to stop

    async def cancel_task():
        """Helper coroutine for task cancellation."""
        if AUDIO_TASK:
            AUDIO_TASK.cancel()
            try:
                await asyncio.wait_for(AUDIO_TASK, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass  # Expected exceptions

    if AUDIO_TASK and ASYNC_LOOP and ASYNC_LOOP.is_running():
    # Run the cancellation coroutine in the correct event loop for audio processing
        future = asyncio.run_coroutine_threadsafe(cancel_task(), ASYNC_LOOP)
        try:
            future.result(timeout=2)  # Wait for cancellation to complete
        except Exception as e:
            console.print(f"[yellow]Warning during task cancellation: {e}[/yellow]")

        console.print("[bold yellow]Web voice interaction disabled.[/bold yellow]")
        socketio.emit('system', {'message': 'Voice interaction disabled.'})

    AUDIO_TASK = None

# --- End New Async Audio Processing ---

# Entry point for running the web server
if __name__ == '__main__':
    # Default port for Flask server
    PORT = 5000

    # Check if port is provided as command line argument for Flask server
    if len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except ValueError:
            console.print(f"[bold red]Invalid port number: {sys.argv[1]}. Using default port 5000.[/bold red]")

    # Start the asyncio loop in a background thread for async operations
    loop_thread = threading.Thread(target=run_async_loop, daemon=True)
    loop_thread.start()

    # Give the loop a moment to start before running Flask server
    time.sleep(1)

    # Try to run the Flask app, with fallback ports if the chosen one is in use for server startup
    MAX_PORT_ATTEMPTS = 10
    for attempt in range(MAX_PORT_ATTEMPTS):
        try:
            console.print(f"[cyan]Attempting to start server on port {PORT}...[/cyan]")

            # Display welcome message with current port for server access
            console.print(Panel.fit(
                "[bold green]Mörk Borg Game Master Web Server[/bold green]\n"
                "An agentic speech-to-speech RPG game master powered by OpenAI\n"
                f"Visit http://localhost:{PORT} to access the web interface",
                title="RPG Game Master"
            ))

            socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
            break  # If successful, exit the loop
        except OSError as e:
            if "Only one usage of each socket address" in str(e) and attempt < MAX_PORT_ATTEMPTS - 1:
                console.print(f"[yellow]Port {PORT} is already in use. Trying port {PORT+1}...[/yellow]")
                PORT += 1
            else:
                console.print(f"[bold red]Failed to start server: {e}[/bold red]")
                sys.exit(1)
