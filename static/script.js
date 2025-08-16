document.addEventListener('DOMContentLoaded', function() {
    const startButton = document.getElementById('startButton');
    const stopButton = document.getElementById('stopButton');
    const listeningIndicator = document.querySelector('.listening-indicator');
    const statusDiv = document.getElementById('status');
    const historyDiv = document.getElementById('history');

    let isCurrentlyListening = false;
    let lastHistoryCount = 0;

    // --- Web Audio API for voice visualization ---
    let audioContext;
    let analyser;
    let mediaStreamSource;

    function setupAudioVisualizer() {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(function(stream) {
                    audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    analyser = audioContext.createAnalyser();
                    mediaStreamSource = audioContext.createMediaStreamSource(stream);

                    mediaStreamSource.connect(analyser);

                    analyser.fftSize = 256;
                    const bufferLength = analyser.frequencyBinCount;
                    const dataArray = new Uint8Array(bufferLength);

                    function updateVisualizer() {
                        if (isCurrentlyListening) {
                            analyser.getByteFrequencyData(dataArray);
                            let sum = dataArray.reduce((acc, val) => acc + val, 0);
                            let average = sum / bufferLength;

                            // Map the average volume to a scale value
                            const minScale = 1;
                            const maxScale = 1.1;
                            const scale = minScale + (average / 150) * (maxScale - minScale);
                            
                            // Apply the scale and color animation
                            listeningIndicator.style.transform = `translate(-50%, -50%) scale(${scale})`;
                        }
                        requestAnimationFrame(updateVisualizer);
                    }

                    updateVisualizer();
                })
                .catch(function(err) {
                    console.error('Microphone access was denied:', err);
                    statusDiv.textContent = 'Microphone access denied. Please allow to use the visualizer.';
                });
        }
    }

    function autoStart() {
        if (!isCurrentlyListening) {
            startButton.click();
        }
    }
    setTimeout(autoStart, 100);

    // --- Expose programmatic button triggers ---
    window.startListening = function() {
        if (!isCurrentlyListening) startButton.click();
    };
    window.stopListening = function() {
        if (isCurrentlyListening) stopButton.click();
    };

    // --- Button Click Event Handlers ---
    startButton.addEventListener('click', function() {
        fetch('/start_listening', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'listening' || data.status === 'already listening') {
                    isCurrentlyListening = true;
                    startButton.disabled = true;
                    stopButton.disabled = false;
                    
                    // Show the indicator and start the visualizer
                    listeningIndicator.style.display = 'block';
                    listeningIndicator.classList.add('active'); // Add the active class for color animation
                    setupAudioVisualizer();
                    
                    statusDiv.textContent = 'Listening...';
                    updateHistory();
                } else {
                    statusDiv.textContent = 'Failed to start listening.';
                }
            });
    });

    stopButton.addEventListener('click', function() {
        fetch('/stop_listening', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'stopped') {
                    isCurrentlyListening = false;
                    startButton.disabled = false;
                    stopButton.disabled = true;

                    // Hide the indicator and reset its state
                    listeningIndicator.style.display = 'none';
                    listeningIndicator.classList.remove('active'); // Remove the active class
                    listeningIndicator.style.transform = `translate(-50%, -50%) scale(1)`;
                    
                    statusDiv.textContent = 'Not listening.';
                } else {
                    statusDiv.textContent = 'Failed to stop listening.';
                }
            });
    });

    // --- Assistant State Polling (sync start/stop buttons with backend) ---
    let lastListeningState = null;
    function pollAssistantState() {
        fetch('/assistant_state')
            .then(response => response.json())
            .then(data => {
                if (lastListeningState === null) {
                    lastListeningState = data.is_listening;
                } else if (lastListeningState !== data.is_listening) {
                    lastListeningState = data.is_listening;
                    if (data.is_listening) {
                        window.startListening();
                    } else {
                        window.stopListening();
                    }
                }
            })
            .finally(() => setTimeout(pollAssistantState, 1000));
    }
    pollAssistantState();

    // --- Conversation History Chatbox Modal ---
    const showHistoryBtn = document.getElementById('showHistoryBtn');
    const chatboxModal = document.getElementById('chatbox-modal');
    const closeChatboxBtn = document.getElementById('closeChatboxBtn');
    const chatboxContent = document.getElementById('chatbox-content');

    function renderChatbox(history) {
        if (!chatboxContent) return;
        chatboxContent.innerHTML = '';
        history.forEach(item => {
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('chat-message');
            msgDiv.style.margin = '8px 0';
            msgDiv.style.padding = '8px 12px';
            msgDiv.style.borderRadius = '16px';
            msgDiv.style.maxWidth = '75%';
            msgDiv.style.wordBreak = 'break-word';
            if (item.role === 'user') {
                msgDiv.style.background = '#e6f7fa'; // lighter blue
                msgDiv.style.color = '#111';
                msgDiv.style.alignSelf = 'flex-end';
                msgDiv.style.marginLeft = 'auto';
            } else if (item.role === 'assistant') {
                msgDiv.style.background = '#f3f3f3';
                msgDiv.style.color = '#111';
                msgDiv.style.alignSelf = 'flex-start';
                msgDiv.style.marginRight = 'auto';
            }
            msgDiv.textContent = item.content;
            chatboxContent.appendChild(msgDiv);
        });
        chatboxContent.scrollTop = chatboxContent.scrollHeight;
    }

    showHistoryBtn.addEventListener('click', function() {
        fetch('/interaction_history')
            .then(response => response.json())
            .then(data => {
                renderChatbox(data.history);
                chatboxModal.style.display = 'flex';
            });
    });
    closeChatboxBtn.addEventListener('click', function() {
        chatboxModal.style.display = 'none';
    });

    // --- Conversation History Polling ---
    function updateHistory() {
        if (isCurrentlyListening) {
            fetch('/interaction_history')
                .then(response => response.json())
                .then(data => {
                    if (data.history.length > lastHistoryCount) {
                        renderHistory(data.history);
                        lastHistoryCount = data.history.length;
                    }
                })
                .finally(() => {
                    setTimeout(updateHistory, 1000);
                });
        }
    }

    function renderHistory(history) {
        const historyContent = document.getElementById('history-content');
        if (!historyContent) return;
        historyContent.innerHTML = '';
        history.forEach(item => {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message');
            if (item.role === 'user') {
                messageDiv.classList.add('user-message');
            } else if (item.role === 'assistant') {
                messageDiv.classList.add('assistant-message');
            }
            messageDiv.textContent = item.content;
            historyContent.appendChild(messageDiv);
        });
        // Auto-scroll to bottom on new message
        historyContent.scrollTop = historyContent.scrollHeight;
    }
});