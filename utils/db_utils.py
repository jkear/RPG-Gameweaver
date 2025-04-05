"""
Database utility functions for the RPG Game Master.
Uses ChromaDB for storing game state, characters, and history.
"""
import json
import chromadb
from rich.console import Console

# Create console instance for pretty printing
console = Console()

# pylint: disable=no-member
class GameDatabase:
    """
    Game database using ChromaDB for persistent storage of game state,
    character data, and game history events.
    """
    def __init__(self, collection_name="rpg_gamemaster", persist_directory="./chroma_db"):
        """
        Initialize the ChromaDB client with persistence
        """
        # Pre-declare instance attributes for pylint
        self.client = None
        self.game_state_collection = None
        self.characters_collection = None
        self.game_history_collection = None
        try:
            self.client = chromadb.PersistentClient(path=persist_directory)
            console.print(f"[green]ChromaDB client initialized. Persistence directory: {persist_directory}[/green]")
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error initializing ChromaDB client: {e}[/bold red]")
            raise  # Re-raise the exception to halt execution if DB fails

        # Create or get collections
        self._initialize_collection(f"{collection_name}_state", "game_state_collection")
        self._initialize_collection(f"{collection_name}_characters", "characters_collection")
        self._initialize_collection(f"{collection_name}_history", "game_history_collection")

    def _initialize_collection(self, name, attribute_name):
        """Helper to initialize a collection"""
        try:
            collection = self.client.get_or_create_collection(name=name)
            setattr(self, attribute_name, collection)
            console.print(f"[green]Collection '{name}' loaded/created successfully.[/green]")
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error initializing collection '{name}': {e}[/bold red]")
            raise

    def store_game_state(self, state_data):
        """
        Store the current game state in ChromaDB
        """
        try:
            state_json = json.dumps(state_data)
            # Use upsert for simplicity (creates if not exists, updates if exists)
            self.game_state_collection.upsert(
                ids=["game_state"],
                documents=[state_json],  # Note: documents must be a list
                metadatas=[{"type": "game_state"}]  # Note: metadatas must be a list
            )
            console.print("[bold green]Game state stored/updated in database[/bold green]")
            return True
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Error encoding game state to JSON: {e}[/bold red]")
            return False
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error storing game state in ChromaDB: {e}[/bold red]")
            return False

    def load_game_state(self):
        """
        Load the current game state from ChromaDB
        """
        try:
            result = self.game_state_collection.get(ids=["game_state"], limit=1)
            if result and result.get('documents'):
                return json.loads(result['documents'][0])
            console.print("[yellow]No existing game state found in database.[/yellow]")
            return None
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Error decoding game state from JSON: {e}[/bold red]")
            return None
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error loading game state from ChromaDB: {e}[/bold red]")
            return None

    def create_character_entity(self, character_id, character_data, character_description):
        """
        Create a character entity in ChromaDB
        """
        try:
            character_json = json.dumps(character_data)
            # Use upsert to handle potential re-creation
            self.characters_collection.upsert(
                ids=[character_id],
                documents=[character_description],
                metadatas=[{"data": character_json, "type": "character"}]
            )
            console.print(f"[bold green]Character '{character_id}' created/updated in database[/bold green]")
            return True
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Error encoding character data to JSON for {character_id}: {e}[/bold red]")
            return False
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error creating character entity '{character_id}' in ChromaDB: {e}[/bold red]")
            return False

    def get_character_entity(self, character_id):
        """
        Get a character entity from ChromaDB
        """
        try:
            result = self.characters_collection.get(ids=[character_id], limit=1)
            if result and result.get('metadatas'):
                # Combine the document (description) with the data
                character_data = json.loads(result['metadatas'][0]['data'])
                character_data["description"] = result['documents'][0]
                return character_data
            console.print(f"[yellow]Character '{character_id}' not found in database.[/yellow]")
            return None
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Error decoding character data for {character_id}: {e}[/bold red]")
            return None
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error getting character '{character_id}' from ChromaDB: {e}[/bold red]")
            return None

    def list_characters(self):
        """
        List all characters in the database
        """
        try:
            result = self.characters_collection.get(where={"type": "character"}, limit=100)
            characters = []
            if result and result.get('ids'):
                for i, character_id in enumerate(result['ids']):
                    try:
                        character_data = json.loads(result['metadatas'][i]['data'])
                        character_data["id"] = character_id
                        character_data["description"] = result['documents'][i]
                        characters.append(character_data)
                    except json.JSONDecodeError as e:
                        console.print(f"[bold red]Error decoding data for character {character_id}: {e}[/bold red]")
                    except IndexError:
                        console.print(
                            f"[bold red]Mismatch in data for character {character_id}. Skipping.[/bold red]"
                        )
            return characters
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error listing characters from ChromaDB: {e}[/bold red]")
            return []

    def add_game_event(self, event_type, event_description, metadata=None):
        """
        Add a game event to the history collection
        """
        try:
            # Generate a unique ID for the event based on current count
            current_count = self.game_history_collection.count()
            event_id = f"event_{current_count + 1}"
            # Create metadata
            event_metadata = {"type": event_type}
            if metadata:
                event_metadata.update(metadata)
            # Add event to collection
            self.game_history_collection.add(
                ids=[event_id],
                documents=[event_description],
                metadatas=[event_metadata]
            )
            console.print(f"[bold green]Event '{event_id}' added to game history: {event_type}[/bold green]")
            return event_id
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error adding game event to ChromaDB: {e}[/bold red]")
            return None

    def get_game_history(self, limit=20, event_type=None):
        """
        Get recent game history events
        """
        try:
            query_params = {"limit": limit}
            if event_type:
                query_params["where"] = {"type": event_type}
            result = self.game_history_collection.get(**query_params)
            events = []
            if result and result.get('ids'):
                for i, event_id in enumerate(result['ids']):
                    try:
                        events.append({
                            "id": event_id,
                            "type": result['metadatas'][i]['type'],
                            "description": result['documents'][i],
                            "metadata": result['metadatas'][i]
                        })
                    except IndexError:
                        console.print(f"[bold red]Mismatch in data for event {event_id}. Skipping.[/bold red]")
            # Sort events by ID (assuming chronological order based on ID generation)
            try:
                events.sort(key=lambda x: int(x['id'].split('_')[1]))
            except (ValueError, IndexError):
                console.print("[yellow]Could not sort history events by ID.[/yellow]")
                # Handle cases where ID format might be unexpected
            return events
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error getting game history from ChromaDB: {e}[/bold red]")
            return []

    def search_game_content(self, query, limit=5):
        """
        Search game content across characters and history using vector search
        """
        results = {"characters": [], "history": []}
        try:
            # Search characters
            character_results = self.characters_collection.query(query_texts=[query], n_results=limit)
            if character_results and character_results.get('ids') and character_results['ids'][0]:
                for i, character_id in enumerate(character_results['ids'][0]):
                    try:
                        results["characters"].append({
                            "id": character_id,
                            "description": character_results['documents'][0][i],
                            "data": json.loads(character_results['metadatas'][0][i]['data']),
                            "distance": character_results['distances'][0][i]
                                if character_results.get('distances') else None
                        })
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        console.print(
                            f"[bold red]Error processing character result {character_id}: {e}[/bold red]"
                        )
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error searching characters in ChromaDB: {e}[/bold red]")
        try:
            # Search history
            history_results = self.game_history_collection.query(query_texts=[query], n_results=limit)
            if history_results and history_results.get('ids') and history_results['ids'][0]:
                for i, event_id in enumerate(history_results['ids'][0]):
                    try:
                        results["history"].append({
                            "id": event_id,
                            "description": history_results['documents'][0][i],
                            "type": history_results['metadatas'][0][i]['type'],
                            "distance": history_results['distances'][0][i]
                                if history_results.get('distances') else None
                        })
                    except (IndexError, KeyError) as e:
                        console.print(f"[bold red]Error processing history result {event_id}: {e}[/bold red]")
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[bold red]Error searching history in ChromaDB: {e}[/bold red]")
        return results
