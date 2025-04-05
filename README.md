# RPG Game Weaver

An agentic speech-to-speech RPG game master powered by OpenAI GPT-4o and speech technologies. This application allows you to play tabletop RPGs using voice commands and receive spoken responses from an AI game master.

## Features

- **Speech-to-Speech Interaction**: Talk to the AI game master and hear responses
- **Persistent Game State**: Games are saved in a ChromaDB database
- **PDF & Text Game File Support**: Import RPG content from various file formats
- **Voice Character Generation**: Different character voices for NPCs and monsters
- **Dice Rolling**: Support for various dice notations (d20, 2d6+3, etc.)
- **Game History**: Track and review game events
- **Web Interface**: Browser-based GUI for easier interaction

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Add your OpenAI API key to a `.env` file in the project root:

```
OPENAI_API_KEY=your_api_key_here
```

3. Add game files to the `game_files` directory (PDF, TXT files work best)

## Usage

### Terminal Application
Run the application in terminal mode:

```bash
python rpg_gameweaver_core.py
```

### Web Interface
Run the web server for browser access:

```bash
python rpg_gameweaver_server.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

### Commands

- `help` - Show this help message
- `start` - Start or resume a game
- `players` - List current players
- `games` - List and select available game files
- `voice on` - Enable speech recognition
- `voice off` - Disable speech recognition
- `save` - Save current game state
- `history` - Show recent game history
- `roll <dice>` - Roll dice (e.g., "roll d20" or "roll 2d6")
- `exit` or `quit` - Exit the application

## Project Structure

- `rpg_gameweaver_core.py` - Main application entry point (CLI version)
- `rpg_gameweaver_server.py` - Flask web server for browser interface
- `templates/` - HTML templates for web interface
- `static/` - CSS and JavaScript files for web interface
- `utils/` - Utility modules:
  - `audio_utils.py` - Audio recording and playback
  - `db_utils.py` - ChromaDB database operations
  - `file_utils.py` - File import and parsing
  - `voice_utils.py` - Speech-to-text and text-to-speech processing
- `game_files/` - Directory for game content (PDF, TXT)
- `chroma_db/` - ChromaDB persistence directory (created on first run)

## Adding New Game Files

Place your RPG game files in the `game_files` directory. Both PDF and text files are supported. When starting a new game, you'll be prompted to select from available game files.

## Web Interface Features

The web interface provides a more user-friendly way to interact with the RPG Game Master:

- Rich text display for game interactions
- Easy command input through a text box
- Voice selection dropdowns for character voices
- One-click access to common commands (start, save, etc.)
- Modal displays for player information and game history
- Voice toggle button for enabling/disabling speech input/output
