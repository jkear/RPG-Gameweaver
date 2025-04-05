// RPG Gameweaver - Enhanced Client-side Application
document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const gameOutput = document.getElementById('game-output');
    const commandForm = document.getElementById('command-form');
    const commandInput = document.getElementById('command-input');
    const voiceToggleBtn = document.getElementById('voice-toggle-btn');
    const gmVoiceSelect = document.getElementById('gm-voice');
    const startBtn = document.getElementById('start-btn');
    const saveBtn = document.getElementById('save-btn');
    const playersBtn = document.getElementById('players-btn');
    const historyBtn = document.getElementById('history-btn');
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const closeModalBtn = document.querySelector('.close');
    const tabButtons = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');
    const showEnemyHpToggle = document.getElementById('show-enemy-hp-toggle');
    const enemyList = document.getElementById('enemy-list');

    // Initialize Socket.io connection
    const socket = io();

    // Game state
    let voiceEnabled = false;
    let pc = null; // RTCPeerConnection
    let dc = null; // RTCDataChannel
    let remoteAudioEl = null; // Audio element for remote stream
    let localStream = null; // User's microphone stream
    let gameState = {
        worldMap: null,
        currentLocation: null,
        inBattle: false,
        battleState: null,
        players: [],
        quests: []
    };

    // Functions to append messages to the terminal
    function appendMessage(message, type) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', type);
        messageElement.innerHTML = message;

        gameOutput.appendChild(messageElement);

        // Auto-scroll to the bottom
        gameOutput.scrollTop = gameOutput.scrollHeight;
    }

    function appendSystemMessage(message) {
        appendMessage(message, 'system-message');
    }

    function appendPlayerMessage(message) {
        appendMessage(`> ${message}`, 'player-message');
    }

    function appendGMMessage(message) {
        // Remove voice instruction patterns like GM [whispering, shadowy]: before displaying
        const cleanedMessage = message.replace(/([A-Za-z]+)(\s*\[[^\]]+\]):/, '$1:');
        appendMessage(cleanedMessage, 'gm-message');
    }

    function appendErrorMessage(message) {
        appendMessage(`Error: ${message}`, 'error-message');
    }

    // Handle command submission
    commandForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const command = commandInput.value.trim();
        if (!command) return;

        // Clear input field
        commandInput.value = '';

        // Display the command in the terminal
        appendPlayerMessage(command);

        // Send the command to the server
        socket.emit('command', {
            command: command,
            voiceSettings: {
                enabled: voiceEnabled,
                gmVoice: gmVoiceSelect.value
            }
        });
    });

    // --- Enhanced Map Tab Functionality ---
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');

            // Deactivate all tabs and content
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activate the clicked tab and corresponding content
            button.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
            
            // If switching to a map tab, trigger appropriate load events
            if (targetTab === 'world-map') {
                console.log("World map activated");
                socket.emit('get_map_data', { type: 'world' });
            } else if (targetTab === 'local-map') {
                console.log("Local map activated");
                socket.emit('get_map_data', { type: 'local', location: gameState.currentLocation });
            } else if (targetTab === 'battle-screen') {
                console.log("Battle screen activated");
                if (gameState.inBattle) {
                    socket.emit('get_battle_state');
                }
            }
        });
    });

    // --- Map Controls ---
    // World Map Controls
    const zoomInBtn = document.getElementById('zoom-in');
    const zoomOutBtn = document.getElementById('zoom-out');
    const centerMapBtn = document.getElementById('center-map');
    const mapContainer = document.querySelector('.map-container');

    // Map zoom functionality
    let currentZoom = 1;
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => {
            if (currentZoom < 2) { // Limit max zoom
                currentZoom += 0.2;
                updateMapZoom();
            }
        });
    }

    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => {
            if (currentZoom > 0.5) { // Limit min zoom
                currentZoom -= 0.2;
                updateMapZoom();
            }
        });
    }

    if (centerMapBtn) {
        centerMapBtn.addEventListener('click', () => {
            // Reset any pan/offset here
            currentZoom = 1;
            updateMapZoom();
        });
    }

    function updateMapZoom() {
        const mapImages = document.querySelectorAll('.map-image');
        mapImages.forEach(img => {
            img.style.transform = `scale(${currentZoom})`;
            img.style.transformOrigin = 'center';
        });
    }

    // Map rendering functions
    function renderWorldMap(mapData) {
        if (!mapData) return;
        
        // In a real implementation, we would render the world map based on the data
        // For now, we'll just update some placeholder text
        const worldMapEl = document.getElementById('world-map');
        if (worldMapEl) {
            const worldMapName = mapData.name || "Unknown Realm";
            const worldMapDesc = document.createElement('div');
            worldMapDesc.className = 'map-description';
            worldMapDesc.innerHTML = `<h3>${worldMapName}</h3>
                <p>A dark, dying world on the brink of apocalypse.</p>`;
            
            // Replace any existing description
            const existingDesc = worldMapEl.querySelector('.map-description');
            if (existingDesc) {
                existingDesc.replaceWith(worldMapDesc);
            } else {
                worldMapEl.appendChild(worldMapDesc);
            }
        }
    }

    // Room selector functionality
    const roomSelector = document.getElementById('room-selector');
    if (roomSelector) {
        roomSelector.addEventListener('change', (e) => {
            const selectedRoom = e.target.value;
            console.log(`Room changed to: ${selectedRoom}`);
            
            // Request the room data from the server
            socket.emit('get_map_data', { type: 'local', location: selectedRoom });
            
            // For demo purposes, change the description based on selection
            const roomDescriptionEl = document.querySelector('.room-description p');
            if (roomDescriptionEl) {
                if (selectedRoom === 'tavern') {
                    roomDescriptionEl.textContent = 'The tavern is dimly lit with oil lamps, casting long shadows across the wooden floor. A fire crackles in the hearth, providing warmth to weary travelers. The air is thick with pipe smoke and the scent of ale.';
                } else if (selectedRoom === 'dungeon-entrance') {
                    roomDescriptionEl.textContent = 'Cold air flows from the ancient stone archway before you. Moss-covered stairs descend into darkness, and the distant sound of dripping water echoes from below. The entrance is marked with faded warnings in a language long forgotten.';
                } else if (selectedRoom === 'crypt') {
                    roomDescriptionEl.textContent = 'The abandoned crypt is deathly silent. Stone sarcophagi line the walls, their lids covered in dust and cobwebs. The air is stale and carries the scent of decay. Strange symbols are etched into the floor, forming a circular pattern in the center of the room.';
                }
            }
        });
    }

    // --- Battle Screen Functionality ---
    const initiativeRollBtn = document.getElementById('initiative-roll');
    const nextTurnBtn = document.getElementById('next-turn');
    
    if (initiativeRollBtn) {
        initiativeRollBtn.addEventListener('click', () => {
            // Send a roll initiative command to the server
            socket.emit('command', {
                command: 'roll initiative'
            });
            appendSystemMessage("Rolling initiative for all combatants...");
        });
    }
    
    if (nextTurnBtn) {
        nextTurnBtn.addEventListener('click', () => {
            // Move to next turn in combat
            console.log("Advancing to next turn");
            const activeTurnEl = document.querySelector('.active-turn');
            if (activeTurnEl) {
                activeTurnEl.classList.remove('active-turn');
                let nextTurn = activeTurnEl.nextElementSibling;
                if (!nextTurn) {
                    // If at the end of the list, loop back to first combatant
                    nextTurn = activeTurnEl.parentElement.firstElementChild;
                }
                if (nextTurn) {
                    nextTurn.classList.add('active-turn');
                    const combatantName = nextTurn.querySelector('.combatant-name').textContent;
                    appendSystemMessage(`It's now ${combatantName}'s turn.`);
                    
                    // Inform the server about turn change
                    socket.emit('battle_action', {
                        action: 'next_turn',
                        combatant: combatantName
                    });
                }
            }
        });
    }

    // Target button functionality
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('target-btn')) {
            const combatantEl = e.target.closest('li');
            const combatantName = combatantEl.querySelector('.combatant-name').textContent;
            appendSystemMessage(`Targeting ${combatantName}`);
            
            // Toggle targeted class on the combatant
            document.querySelectorAll('.combatant-list li').forEach(li => {
                li.classList.remove('targeted');
            });
            combatantEl.classList.add('targeted');
            
            // Inform the server about target selection
            socket.emit('battle_action', {
                action: 'target',
                target: combatantName
            });
        }
    });

    // --- Quest Tracker Functionality ---
    const questFilterSelect = document.getElementById('quest-filter');
    const addQuestBtn = document.getElementById('add-quest');
    
    if (questFilterSelect) {
        questFilterSelect.addEventListener('change', (e) => {
            const filter = e.target.value;
            console.log(`Quest filter changed to: ${filter}`);
            const questItems = document.querySelectorAll('.quest-item');
            
            questItems.forEach(item => {
                if (filter === 'all') {
                    item.style.display = 'block';
                } else if (filter === 'active' && item.classList.contains('active')) {
                    item.style.display = 'block';
                } else if (filter === 'completed' && !item.classList.contains('active')) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }
    
    if (addQuestBtn) {
        addQuestBtn.addEventListener('click', () => {
            // Open a modal for quest creation
            showModal('Add New Quest', `
                <div class="quest-form">
                    <div class="form-group">
                        <label for="quest-title">Quest Title:</label>
                        <input type="text" id="quest-title" placeholder="Enter quest title">
                    </div>
                    <div class="form-group">
                        <label for="quest-description">Description:</label>
                        <textarea id="quest-description" placeholder="Enter quest description"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="quest-objectives">Objectives (one per line):</label>
                        <textarea id="quest-objectives" placeholder="Enter objectives, one per line"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="quest-rewards">Rewards (one per line):</label>
                        <textarea id="quest-rewards" placeholder="Enter rewards, one per line"></textarea>
                    </div>
                    <button id="save-quest-btn" class="primary-btn">Save Quest</button>
                </div>
            `);
            
            // Add event listener for the save button
            document.getElementById('save-quest-btn').addEventListener('click', () => {
                const title = document.getElementById('quest-title').value;
                const description = document.getElementById('quest-description').value;
                const objectives = document.getElementById('quest-objectives').value.split('\n').filter(line => line.trim());
                const rewards = document.getElementById('quest-rewards').value.split('\n').filter(line => line.trim());
                
                if (!title || !description || objectives.length === 0) {
                    alert('Please fill in the required fields (title, description, and at least one objective).');
                    return;
                }
                
                // Send quest data to server
                socket.emit('add_quest', {
                    title,
                    description,
                    objectives,
                    rewards
                });
                
                closeModal();
                appendSystemMessage(`New quest "${title}" added.`);
            });
        });
    }

    // --- Character Info Functionality ---
    const characterSelector = document.getElementById('character-selector');
    
    if (characterSelector) {
        characterSelector.addEventListener('change', (e) => {
            const filter = e.target.value;
            console.log(`Character filter changed to: ${filter}`);
            const characterCards = document.querySelectorAll('.character-card');
            
            characterCards.forEach(card => {
                if (filter === 'all') {
                    card.style.display = 'flex';
                } else if (filter === 'party' && card.classList.contains('player')) {
                    card.style.display = 'flex';
                } else if (filter === 'npcs' && card.classList.contains('npc')) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }

    // --- Enemy HP Toggle Functionality ---
    if (showEnemyHpToggle && enemyList) {
        showEnemyHpToggle.addEventListener('change', () => {
            const showHp = showEnemyHpToggle.checked;
            // Find all HP elements and toggle buttons across the UI
            const hpElements = document.querySelectorAll('.enemy-hp, .combatant-stats');
            const hpToggleButtons = document.querySelectorAll('.toggle-hp');

            hpElements.forEach(el => {
                // Toggle visibility based on checkbox
                el.style.visibility = showHp ? 'visible' : 'hidden';
            });
             // Show/hide individual toggle buttons
            hpToggleButtons.forEach(btn => {
                 btn.style.display = showHp ? 'inline-block' : 'none';
            });
        });

        // Initial state based on checkbox (default off)
        const initialShowHp = showEnemyHpToggle.checked;
        document.querySelectorAll('.enemy-hp, .combatant-stats').forEach(el => {
            el.style.visibility = initialShowHp ? 'visible' : 'hidden';
        });
        document.querySelectorAll('.toggle-hp').forEach(btn => {
            btn.style.display = initialShowHp ? 'inline-block' : 'none';
        });

        // HP editing functionality
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('toggle-hp')) {
                const parentEl = e.target.closest('li');
                const hpSpan = parentEl?.querySelector('.enemy-hp');
                if (hpSpan) {
                    const combatantName = parentEl.querySelector('.combatant-name').textContent;
                    
                    // Simple prompt-based HP editing
                    const currentHP = hpSpan.textContent;
                    const newHP = prompt(`Enter new HP for ${combatantName} (current: ${currentHP}):`, currentHP);
                    
                    if (newHP !== null && !isNaN(newHP)) {
                        hpSpan.textContent = newHP;
                        appendSystemMessage(`Updated ${combatantName}'s HP to ${newHP}`);
                        
                        // Inform the server about the HP change
                        socket.emit('battle_action', {
                            action: 'update_hp',
                            target: combatantName,
                            hp: newHP
                        });
                    }
                }
            }
        });
    }
    // --- End Enhanced Map/Game Logic ---


    // --- WebRTC Connection Logic ---

    async function initWebRTCConnection() {
        if (pc) {
            console.log("WebRTC connection already exists or is being established.");
            return;
        }
        appendSystemMessage("Initializing WebRTC connection with OpenAI Realtime API...");

        try {
            // 1. Get an ephemeral key from our server
            const tokenResponse = await fetch("/session");
            if (!tokenResponse.ok) {
                const errorData = await tokenResponse.json();
                throw new Error(`Failed to get session key: ${errorData.error || tokenResponse.statusText}`);
            }
            const data = await tokenResponse.json();
            const EPHEMERAL_KEY = data.client_secret.value;
            console.log("Ephemeral key received.");

            // 2. Create a peer connection
            pc = new RTCPeerConnection();

            // 3. Set up to play remote audio from the model
            if (!remoteAudioEl) {
                remoteAudioEl = document.createElement("audio");
                remoteAudioEl.autoplay = true;
                document.body.appendChild(remoteAudioEl); // Append to body to ensure playback
            }
            pc.ontrack = e => {
                console.log("Received remote audio track.");
                if (remoteAudioEl.srcObject !== e.streams[0]) {
                    remoteAudioEl.srcObject = e.streams[0];
                    remoteAudioEl.play().catch(e => console.error("Error playing remote audio:", e));
                }
            };

            // 4. Add local audio track for microphone input
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
                console.log("Microphone access granted and track added.");
            } catch (err) {
                console.error("Error accessing microphone:", err);
                appendErrorMessage("Microphone access denied. WebRTC voice input will not work.");
                // Continue without local audio track if necessary, but log error
                // throw new Error("Microphone access denied."); // Option to halt setup
            }


            // 5. Set up data channel for sending and receiving events
            dc = pc.createDataChannel("oai-events");
            dc.onopen = () => {
                console.log("WebRTC data channel opened.");
                appendSystemMessage("WebRTC data channel connected.");
            };
            dc.onclose = () => {
                console.log("WebRTC data channel closed.");
                appendSystemMessage("WebRTC data channel disconnected.");
            };
            dc.onerror = (e) => {
                console.error("WebRTC data channel error:", e);
                appendErrorMessage(`WebRTC data channel error: ${e}`);
            };
            dc.onmessage = (e) => {
                // Realtime server events appear here!
                console.log("Received message on data channel:", e.data);
                // TODO: Process events from OpenAI (e.g., transcriptions, agent responses)
                // This part requires knowing the specific event format from OpenAI Realtime API
                try {
                    const eventData = JSON.parse(e.data);
                    // Example: Check for transcription or agent message
                    if (eventData.type === 'transcription') {
                         appendSystemMessage(`Transcription: ${eventData.text}`);
                    } else if (eventData.type === 'agent_response') {
                         appendGMMessage(eventData.text);
                    } else {
                         appendSystemMessage(`Data Channel Event: ${e.data}`);
                    }
                } catch (parseError) {
                     appendSystemMessage(`Data Channel (raw): ${e.data}`);
                }
            };

            // 6. Start the session using the Session Description Protocol (SDP)
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            console.log("Local SDP offer created.");

            // 7. Send offer to OpenAI Realtime API
            const baseUrl = "https://api.openai.com/v1/realtime";
            const model = "gpt-4o-realtime-preview-2024-12-17"; // Use the specified model
            console.log(`Sending SDP offer to ${baseUrl}?model=${model}`);
            const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
                method: "POST",
                body: offer.sdp,
                headers: {
                    Authorization: `Bearer ${EPHEMERAL_KEY}`,
                    "Content-Type": "application/sdp" // Crucial header
                },
            });

            if (!sdpResponse.ok) {
                 const errorText = await sdpResponse.text();
                 console.error("SDP Offer failed:", sdpResponse.status, errorText);
                 throw new Error(`SDP Offer request failed: ${sdpResponse.status} ${errorText}`);
            }

            const answerSdp = await sdpResponse.text();
            console.log("Received SDP answer from OpenAI.");

            // 8. Set the remote description
            const answer = {
                type: "answer",
                sdp: answerSdp,
            };
            await pc.setRemoteDescription(answer);
            console.log("Remote SDP answer set. WebRTC connection established.");
            appendSystemMessage("WebRTC connection to OpenAI established.");
            voiceEnabled = true; // Mark voice as enabled
            updateVoiceToggleButton();

        } catch (error) {
            console.error("Failed to initialize WebRTC connection:", error);
            appendErrorMessage(`WebRTC Initialization Failed: ${error.message}`);
            closeWebRTCConnection(); // Clean up on failure
        }
    }

    function closeWebRTCConnection() {
        if (dc) {
            dc.close();
            dc = null;
        }
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
        }
        if (pc) {
            pc.close();
            pc = null;
        }
        if (remoteAudioEl) {
            remoteAudioEl.srcObject = null;
        }
        console.log("WebRTC connection closed.");
        appendSystemMessage("WebRTC connection closed.");
        voiceEnabled = false; // Mark voice as disabled
        updateVoiceToggleButton();
    }

    // --- End WebRTC Connection Logic ---


    // Socket.io event handlers
    socket.on('connect', () => {
        appendSystemMessage('Connected to server');
    });

    socket.on('disconnect', () => {
        appendSystemMessage('Disconnected from server');
    });

    socket.on('response', (data) => {
        if (data.error) {
            appendErrorMessage(data.message);
        } else {
            appendGMMessage(data.message);
        }
    });

    socket.on('system', (data) => {
        appendSystemMessage(data.message);
    });

    socket.on('game_state', (data) => {
        if (data.players) {
            showPlayersModal(data.players);
        }
        
        // Update local game state
        if (data.worldMap) {
            gameState.worldMap = data.worldMap;
            renderWorldMap(data.worldMap);
        }
        
        if (data.currentLocation) {
            gameState.currentLocation = data.currentLocation;
        }
        
        if (data.inBattle !== undefined) {
            gameState.inBattle = data.inBattle;
        }
        
        if (data.battleState) {
            gameState.battleState = data.battleState;
        }
    });

    socket.on('map_data', (data) => {
        if (data.type === 'world') {
            gameState.worldMap = data.map;
            renderWorldMap(data.map);
        } else if (data.type === 'local') {
            // Update the local map display
            const roomDescription = document.querySelector('.room-description p');
            if (roomDescription && data.description) {
                roomDescription.textContent = data.description;
            }
        }
    });

    socket.on('history', (data) => {
        if (data.history) {
            showHistoryModal(data.history);
        }
    });

    // Button event handlers
    function updateVoiceToggleButton() {
         if (voiceEnabled) {
            voiceToggleBtn.textContent = 'Voice: ON';
            voiceToggleBtn.classList.remove('off');
            voiceToggleBtn.classList.add('on');
        } else {
            voiceToggleBtn.textContent = 'Voice: OFF';
            voiceToggleBtn.classList.remove('on');
            voiceToggleBtn.classList.add('off');
        }
    }

    voiceToggleBtn.addEventListener('click', () => {
        if (!voiceEnabled) {
            // Start WebRTC connection
            initWebRTCConnection();
            // Button state will be updated by initWebRTCConnection on success/failure
        } else {
            // Close WebRTC connection
            closeWebRTCConnection();
            // Button state will be updated by closeWebRTCConnection
        }
    });

    startBtn.addEventListener('click', () => {
        appendPlayerMessage('start');
        socket.emit('command', {
            command: 'start',
            voiceSettings: {
                enabled: voiceEnabled,
                gmVoice: gmVoiceSelect.value
            }
        });
    });

    saveBtn.addEventListener('click', () => {
        appendPlayerMessage('save');
        socket.emit('command', {
            command: 'save',
            voiceSettings: {
                enabled: voiceEnabled,
                gmVoice: gmVoiceSelect.value
            }
        });
    });

    playersBtn.addEventListener('click', () => {
        appendPlayerMessage('players');
        socket.emit('command', {
            command: 'players',
            voiceSettings: {
                enabled: voiceEnabled,
                gmVoice: gmVoiceSelect.value
            }
        });
    });

    historyBtn.addEventListener('click', () => {
        appendPlayerMessage('history');
        socket.emit('command', {
            command: 'history',
            voiceSettings: {
                enabled: voiceEnabled,
                gmVoice: gmVoiceSelect.value
            }
        });
    });

    // Modal functions
    function showModal(title, content) {
        modalTitle.textContent = title;
        modalBody.innerHTML = content;
        modal.style.display = 'block';
    }

    function closeModal() {
        modal.style.display = 'none';
    }

    closeModalBtn.addEventListener('click', closeModal);

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    function showPlayersModal(players) {
        let content = '<div class="players-list">';

        players.forEach(player => {
            content += `
                <div class="player-card">
                    <h3>${player.character_name}</h3>
                    <p><strong>Player:</strong> ${player.player_name}</p>
                    <p><strong>Health:</strong> ${player.health}</p>
                    <p><strong>Background:</strong> ${player.background}</p>
                    <div class="stats">
                        <p><strong>Stats:</strong></p>
                        <ul>
                            ${Object.entries(player.stats).map(([stat, value]) => `<li>${stat}: ${value}</li>`).join('')}
                        </ul>
                    </div>
                    <div class="inventory">
                        <p><strong>Inventory:</strong></p>
                        ${player.inventory.length ?
                            `<ul>${player.inventory.map(item => `<li>${item}</li>`).join('')}</ul>` :
                            '<p>Empty</p>'}
                    </div>
                </div>
            `;
        });

        content += '</div>';

        showModal('Players', content);
    }

    function showHistoryModal(history) {
        let content = '<div class="history-list">';

        history.forEach(event => {
            content += `
                <div class="history-item">
                    <h4>[${event.type}]</h4>
                    <p>${event.description}</p>
                </div>
            `;
        });

        content += '</div>';

        showModal('Game History', content);
    }

    // Focus the input field on page load
    commandInput.focus();
});
