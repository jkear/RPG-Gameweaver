"""
File utility functions for the RPG Game Master.
Handles loading, saving, and managing game files.
"""
import os
import json
import PyPDF2
from rich.console import Console

# Create console instance for pretty printing
console = Console()

def load_game_file(file_path):
    """
    Load and parse game files (text or PDF) for game content.

    Args:
        file_path: Path to the game file

    Returns:
        str: Content of the file or None if loading failed
    """
    try:
        if file_path.endswith('.pdf'):
            return read_pdf_file(file_path)
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        console.print(f"[bold red]Error: Game file not found at {file_path}[/bold red]")
        return None
    except PermissionError:
        console.print(f"[bold red]Error: Permission denied reading file {file_path}[/bold red]")
        return None
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]Error loading game file {file_path}: {e}[/bold red]")
        return None

def read_pdf_file(file_path):
    """
    Extract text from PDF files.

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text from the PDF file or None if extraction failed
    """
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:  # Check if text extraction was successful
                    text += page_text
                else:
                    console.print(
                        f"[yellow]Warning: Could not extract text from page {page_num + 1} "
                        f"of {file_path}[/yellow]"
                    )
        return text
    except PyPDF2.errors.PdfReadError as e:
        console.print(
            f"[bold red]Error reading PDF file {file_path}: {e}. "
            f"It might be corrupted or password-protected.[/bold red]"
        )
        return None
    except FileNotFoundError:
        # This case should ideally be caught by load_game_file, but added for safety
        console.print(f"[bold red]Error: PDF file not found at {file_path}[/bold red]")
        return None
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]An unexpected error occurred while reading PDF {file_path}: {e}[/bold red]")
        return None

def list_available_games():
    """
    List all available game files in the game_files directory.

    Returns:
        list: List of paths to available game files
    """
    game_files = []
    directory = "game_files"
    try:
        if not os.path.isdir(directory):
            console.print(
                f"[bold yellow]Warning: Game files directory '{directory}' not found. "
                f"Creating it.[/bold yellow]"
            )
            os.makedirs(directory, exist_ok=True)
            return []  # No files if directory didn't exist
        for filename in os.listdir(directory):
            if filename.endswith(('.txt', '.pdf')):
                game_files.append(os.path.join(directory, filename))
        return game_files
    except PermissionError:
        console.print(f"[bold red]Error: Permission denied accessing directory {directory}[/bold red]")
        return []
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]Error listing available games: {e}[/bold red]")
        return []

def save_game_state(state, filename="game_state.json"):
    """
    Save the current game state to a JSON file (as backup).

    Args:
        state: Game state data to save
        filename: Target filename (default: "game_state.json")

    Returns:
        bool: True if save successful, False otherwise
    """
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(state, file, indent=4)
        console.print(f"[bold green]Game state backup saved to {filename}[/bold green]")
        return True
    except TypeError as e:
        console.print(f"[bold red]Error: Could not serialize game state to JSON: {e}[/bold red]")
        return False
    except PermissionError:
        console.print(f"[bold red]Error: Permission denied writing game state file {filename}[/bold red]")
        return False
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]Error saving game state backup to {filename}: {e}[/bold red]")
        return False

def load_game_state(filename="game_state.json"):
    """
    Load a game state from a JSON file (backup).

    Args:
        filename: Source filename (default: "game_state.json")

    Returns:
        dict: Loaded game state or None if loading failed
    """
    if not os.path.exists(filename):
        console.print(f"[yellow]Game state backup file {filename} does not exist.[/yellow]")
        return None
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error decoding JSON from game state file {filename}: {e}[/bold red]")
        return None
    except FileNotFoundError:
        # Should be caught by os.path.exists, but included for robustness
        console.print(f"[yellow]Game state backup file {filename} not found.[/yellow]")
        return None
    except PermissionError:
        console.print(f"[bold red]Error: Permission denied reading game state file {filename}[/bold red]")
        return None
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]Error loading game state backup from {filename}: {e}[/bold red]")
        return None
