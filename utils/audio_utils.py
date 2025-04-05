"""
Audio utility functions for recording, playing, and saving audio.
Uses sounddevice, numpy, soundfile, and pydub for audio processing.
"""
import io  # Standard library imports first
import os
import threading
import base64
import sounddevice as sd  # Third-party imports
import numpy as np
import soundfile as sf
from rich.console import Console

# Create console instance for pretty printing
console = Console()

# Try to import pydub for enhanced audio features
try:
    from pydub import AudioSegment
    from pydub.playback import play as pydub_play
    PYDUB_AVAILABLE = True
    console.print("[green]pydub imported successfully - enhanced audio features available.[/green]")
except ImportError:
    PYDUB_AVAILABLE = False
    console.print("[yellow]pydub not available. Some audio features will be limited.[/yellow]")

def record_audio(duration=5, samplerate=44100):
    """Record audio for a specified duration."""
    console.print(f"Recording audio for {duration} seconds...")
    try:
        # Check if input device is available
        sd.check_input_settings(samplerate=samplerate, channels=1, dtype='int16')
        
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()  # Wait until recording is finished
        console.print("[green]Recording finished.[/green]")
        return recording  # Return numpy array directly
    except sd.PortAudioError as e:
        console.print(f"[bold red]PortAudio Error during recording: {e}[/bold red]")
        console.print("[bold red]Please check your audio input device configuration.[/bold red]")
        return None
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]An unexpected error occurred during recording: {e}[/bold red]")
        return None

def play_audio_from_file(filepath):
    """Play audio from a file path."""
    console.print(f"Playing audio from {filepath}...")
    
    # If pydub is available, use it for better format support
    if PYDUB_AVAILABLE:
        try:
            sound = AudioSegment.from_file(filepath)
            threading.Thread(target=pydub_play, args=(sound,), daemon=True).start()
            console.print("[green]Playback started with pydub.[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]pydub playback failed, falling back to sounddevice: {e}[/yellow]")
            # Continue to fallback method
    
    # Fallback to sounddevice if pydub isn't available or failed
    try:
        data, fs = sf.read(filepath, dtype='float32')
        sd.play(data, fs)
        sd.wait()  # Wait until file is done playing
        console.print("[green]Playback finished.[/green]")
        return True
    except sd.PortAudioError as e:
        console.print(f"[bold red]PortAudio Error during playback: {e}[/bold red]")
        console.print("[bold red]Please check your audio output device configuration.[/bold red]")
        return False
    except sf.SoundFileError as e:
        console.print(f"[bold red]Error reading sound file {filepath}: {e}[/bold red]")
        return False
    except FileNotFoundError:
        console.print(f"[bold red]Error: Audio file not found at {filepath}[/bold red]")
        return False
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]An unexpected error occurred during playback: {e}[/bold red]")
        return False

def save_audio_to_bytes(audio_data, samplerate=44100, file_format='WAV', subtype='PCM_16'):
    """Save audio data (numpy array) to a bytes buffer."""
    console.print(f"Saving audio data to bytes buffer (Format: {file_format})...")
    try:
        buffer = io.BytesIO()
        # Ensure data is in the correct format for soundfile if needed
        # Example: if audio_data is int16, soundfile expects float for WAV PCM_16
        if audio_data.dtype == np.int16 and subtype == 'PCM_16':
            # Convert int16 to float32 for soundfile compatibility
            audio_data_float = audio_data.astype(np.float32) / 32768.0
        else:
            audio_data_float = audio_data  # Assume it's already float or compatible

        sf.write(buffer, audio_data_float, samplerate, format=file_format, subtype=subtype)
        buffer.seek(0)  # Rewind buffer to the beginning
        console.print("[green]Audio data saved to bytes buffer.[/green]")
        return buffer.read()
    except sf.SoundFileError as e:
        console.print(f"[bold red]Error writing audio data to buffer: {e}[/bold red]")
        return None
    except Exception as e:  # pylint: disable=broad-except
        console.print(
            f"[bold red]An unexpected error occurred saving audio to bytes: {e}[/bold red]"
        )
        return None

def save_audio_to_file(audio_data, filename, samplerate=44100, file_format='WAV', subtype='PCM_16'):
    """Save audio data (numpy array) to a file using soundfile."""
    console.print(f"Saving audio data to {filename}...")
    try:
        # Ensure data is in the correct format for soundfile if needed
        if audio_data.dtype == np.int16 and subtype == 'PCM_16':
            audio_data_float = audio_data.astype(np.float32) / 32768.0
        else:
            audio_data_float = audio_data

        sf.write(filename, audio_data_float, samplerate, format=file_format, subtype=subtype)
        console.print(f"[bold green]Audio saved to {filename}[/bold green]")
        return True
    except sf.SoundFileError as e:
        console.print(f"[bold red]Error writing sound file {filename}: {e}[/bold red]")
        return False
    except PermissionError:
        console.print(f"[bold red]Error: Permission denied writing file {filename}[/bold red]")
        return False
    except Exception as e:  # pylint: disable=broad-except
        console.print(f"[bold red]An unexpected error occurred saving audio to file: {e}[/bold red]")
        return False

class SoundManager:
    """Manages sound effects and music for the RPG Game Master."""
    
    def __init__(self, sounds_dir="static/sounds"):
        self.sounds_dir = sounds_dir
        self.sound_cache = {}  # Cache for loaded sounds
        self.current_music = None
        self.music_volume = 0.7  # 70% volume for background music
        self.sfx_volume = 1.0  # 100% volume for sound effects
        
        # Create sounds directory if it doesn't exist
        os.makedirs(sounds_dir, exist_ok=True)
        os.makedirs(os.path.join(sounds_dir, "ambience"), exist_ok=True)
        os.makedirs(os.path.join(sounds_dir, "effects"), exist_ok=True)
        
        # Check if pydub is available
        if not PYDUB_AVAILABLE:
            console.print("[yellow]pydub not available. SoundManager will have limited functionality.[/yellow]")
    
    def load_sound(self, sound_name):
        """Load a sound from file or cache."""
        if not PYDUB_AVAILABLE:
            console.print("[yellow]pydub not available. Cannot load sounds.[/yellow]")
            return None
            
        if sound_name in self.sound_cache:
            return self.sound_cache[sound_name]
            
        # Look in the sounds directory
        sound_path = os.path.join(self.sounds_dir, "effects", f"{sound_name}.mp3")
        if not os.path.exists(sound_path):
            sound_path = os.path.join(self.sounds_dir, "effects", f"{sound_name}.wav")
            
        if not os.path.exists(sound_path):
            console.print(f"[bold yellow]Warning: Sound '{sound_name}' not found.[/bold yellow]")
            return None
            
        # Load and cache the sound
        try:
            sound = AudioSegment.from_file(sound_path)
            self.sound_cache[sound_name] = sound
            return sound
        except Exception as e:
            console.print(f"[bold red]Error loading sound '{sound_name}': {e}[/bold red]")
            return None
    
    def play_sound(self, sound_name):
        """Play a sound effect asynchronously."""
        if not PYDUB_AVAILABLE:
            console.print("[yellow]pydub not available. Cannot play sounds.[/yellow]")
            return False
            
        sound = self.load_sound(sound_name)
        if sound is None:
            return False
            
        # Adjust volume and play in a separate thread
        sound = sound.apply_gain(self.sfx_volume)
        threading.Thread(target=pydub_play, args=(sound,), daemon=True).start()
        return True
    
    def play_themed_sound(self, theme, intensity="medium"):
        """Play a sound based on a theme and intensity."""
        if not PYDUB_AVAILABLE:
            console.print("[yellow]pydub not available. Cannot play themed sounds.[/yellow]")
            return False
            
        # Map themes to appropriate sound effects
        theme_mapping = {
            "combat": {
                "low": ["sword_swing", "dagger_strike"],
                "medium": ["sword_clash", "arrow_impact"],
                "high": ["explosion", "dragon_roar"]
            },
            "mystery": {
                "low": ["wind_whisper", "creak"],
                "medium": ["eerie_wind", "ghostly_moan"],
                "high": ["horror_sting", "demonic_whisper"]
            },
            "tavern": {
                "low": ["cup_down", "chair_move"],
                "medium": ["tavern_chatter", "lute_music"],
                "high": ["tavern_fight", "bar_cheer"]
            }
        }
        
        # Check if we have sounds for this theme
        if theme not in theme_mapping:
            console.print(f"[yellow]No sounds available for theme '{theme}'[/yellow]")
            return False
            
        # Get the sound options for this theme and intensity
        sound_options = theme_mapping.get(theme, {}).get(intensity, [])
        if not sound_options:
            console.print(f"[yellow]No sounds available for theme '{theme}' at intensity '{intensity}'[/yellow]")
            return False
            
        # Pick a random sound from the options
        import random
        sound_name = random.choice(sound_options)
        
        # Play the selected sound
        return self.play_sound(sound_name)
        
    def prepare_sound_for_web(self, sound_name):
        """Prepare a sound for web playback (returns base64 encoded WAV)."""
        if not PYDUB_AVAILABLE:
            console.print("[yellow]pydub not available. Cannot prepare sounds for web.[/yellow]")
            return None
            
        sound = self.load_sound(sound_name)
        if sound is None:
            return None
            
        # Apply volume adjustment
        sound = sound.apply_gain(self.sfx_volume)
        
        # Export to WAV format in memory
        buffer = io.BytesIO()
        sound.export(buffer, format="wav")
        buffer.seek(0)
        
        # Base64 encode for web transport
        b64_encoded = base64.b64encode(buffer.read()).decode('utf-8')
        return {
            'audio': b64_encoded,
            'format': 'wav',
            'encoding': 'base64'
        }
