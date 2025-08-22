// Modern JavaScript for Sylvia Voice Assistant Frontend
// Connects the professional UI to the assistant.py backend

document.addEventListener('DOMContentLoaded', function() {
    // UI Elements
    const voiceCircle = document.getElementById('voice-circle');
    const micIcon = document.getElementById('mic-icon');
    const voiceStatus = document.getElementById('voice-status');
    const statusBadge = document.getElementById('status-badge');
    const statusText = document.getElementById('status-text');
    const statusDot = document.getElementById('status-dot');
    const startBtn = document.getElementById('start-listening');
    const stopBtn = document.getElementById('stop-listening');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const clearChatBtn = document.getElementById('clear-chat');

    // State management
    let isListening = false;
    let isConnected = false;
    let pollInterval = null;
    let conversationHistory = [];

    // Initialize the application
    init();

    function init() {
        setupEventListeners();
        checkBackendConnection();
        startPolling();
        updateUI();
    }

    function setupEventListeners() {
        startBtn.addEventListener('click', startListening);
        stopBtn.addEventListener('click', stopListening);
        clearChatBtn.addEventListener('click', clearChat);
    }

    // Backend connection and communication
    async function checkBackendConnection() {
        try {
            const response = await fetch('/assistant_state');
            if (response.ok) {
                isConnected = true;
                updateConnectionStatus('Connected', 'connected');
            } else {
                isConnected = false;
                updateConnectionStatus('Backend Offline', 'error');
            }
        } catch (error) {
            isConnected = false;
            updateConnectionStatus('Connection Error', 'error');
            console.error('Backend connection error:', error);
        }
    }

    async function startListening() {
        if (!isConnected) {
            showNotification('Backend is not connected. Please start the assistant backend.', 'error');
            return;
        }

        try {
            const response = await fetch('/start_listening', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'success') {
                isListening = true;
                updateUI();
                updateVoiceStatus('Listening for "Sylvia"...');
                animateVoiceCircle('listening');
                showNotification('Voice assistant activated', 'success');
            } else {
                showNotification('Failed to start listening: ' + data.message, 'error');
            }
        } catch (error) {
            showNotification('Error starting voice assistant', 'error');
            console.error('Start listening error:', error);
        }
    }

    async function stopListening() {
        try {
            const response = await fetch('/stop_listening', { method: 'POST' });
            const data = await response.json();
            
            isListening = false;
            updateUI();
            updateVoiceStatus('Say "Sylvia" to activate');
            animateVoiceCircle('idle');
            showNotification('Voice assistant stopped', 'info');
        } catch (error) {
            showNotification('Error stopping voice assistant', 'error');
            console.error('Stop listening error:', error);
        }
    }

    // UI Updates
    function updateUI() {
        if (isListening) {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-flex';
            statusText.textContent = 'Listening';
            statusDot.className = 'status-dot listening';
        } else {
            startBtn.style.display = 'inline-flex';
            stopBtn.style.display = 'none';
            statusText.textContent = isConnected ? 'Ready' : 'Offline';
            statusDot.className = isConnected ? 'status-dot' : 'status-dot error';
        }
    }

    function updateConnectionStatus(text, status) {
        statusText.textContent = text;
        statusDot.className = `status-dot ${status}`;
    }

    function updateVoiceStatus(text) {
        voiceStatus.textContent = text;
    }

    function animateVoiceCircle(state) {
        voiceCircle.className = 'voice-circle';
        if (state === 'listening') {
            voiceCircle.classList.add('listening');
            micIcon.className = 'fas fa-microphone';
        } else if (state === 'speaking') {
            voiceCircle.classList.add('speaking');
            micIcon.className = 'fas fa-volume-up';
        } else {
            micIcon.className = 'fas fa-microphone';
        }
    }

    // Chat functionality
    function addMessage(text, sender, timestamp = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = sender === 'sylvia' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = text;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = timestamp || new Date().toLocaleTimeString();
        
        contentDiv.appendChild(textDiv);
        contentDiv.appendChild(timeDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Store in conversation history
        conversationHistory.push({
            text: text,
            sender: sender,
            timestamp: timestamp || new Date().toISOString()
        });
    }

    function showTypingIndicator() {
        typingIndicator.classList.add('active');
    }

    function hideTypingIndicator() {
        typingIndicator.classList.remove('active');
    }

    function clearChat() {
        chatMessages.innerHTML = `
            <div class="message sylvia-message">
                <div class="message-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <div class="message-text">Hello! I'm Sylvia, your voice assistant. Say "Sylvia" to activate me and start our conversation.</div>
                    <div class="message-time">Just now</div>
                </div>
            </div>
        `;
        conversationHistory = [];
    }

    // Polling for real-time updates
    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        
        pollInterval = setInterval(async () => {
            await checkBackendConnection();
            await pollForUpdates();
        }, 2000); // Poll every 2 seconds
    }

    async function pollForUpdates() {
        if (!isConnected) return;
        
        try {
            const response = await fetch('/interaction_history');
            const data = await response.json();
            
            if (data.status === 'success' && data.history) {
                updateConversationHistory(data.history);
            }
            
            // Check assistant state
            const stateResponse = await fetch('/assistant_state');
            const stateData = await stateResponse.json();
            
            if (stateData.status === 'success') {
                updateAssistantState(stateData);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }

    function updateConversationHistory(newHistory) {
        // Only add new messages to avoid duplicates
        const existingCount = conversationHistory.length;
        const newMessages = newHistory.slice(existingCount);
        
        newMessages.forEach(interaction => {
            if (interaction.user_input && interaction.user_input !== 'no_speech_detected') {
                addMessage(interaction.user_input, 'user', interaction.timestamp);
            }
            if (interaction.assistant_response) {
                showTypingIndicator();
                setTimeout(() => {
                    hideTypingIndicator();
                    addMessage(interaction.assistant_response, 'sylvia', interaction.timestamp);
                    animateVoiceCircle('speaking');
                    setTimeout(() => animateVoiceCircle(isListening ? 'listening' : 'idle'), 2000);
                }, 1000);
            }
        });
    }

    function updateAssistantState(stateData) {
        if (stateData.is_listening !== isListening) {
            isListening = stateData.is_listening;
            updateUI();
            
            if (isListening) {
                updateVoiceStatus('Listening...');
                animateVoiceCircle('listening');
            } else {
                updateVoiceStatus('Say "Sylvia" to activate');
                animateVoiceCircle('idle');
            }
        }
    }

    // Notification system
    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 3000);
    }

    function getNotificationIcon(type) {
        switch (type) {
            case 'success': return 'check-circle';
            case 'error': return 'exclamation-circle';
            case 'warning': return 'exclamation-triangle';
            default: return 'info-circle';
        }
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (pollInterval) clearInterval(pollInterval);
    });

    // Add notification styles dynamically
    const notificationStyles = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            z-index: 1000;
            border-left: 4px solid #667eea;
        }
        
        .notification.show {
            transform: translateX(0);
        }
        
        .notification-success {
            border-left-color: #10b981;
            color: #065f46;
        }
        
        .notification-error {
            border-left-color: #ef4444;
            color: #991b1b;
        }
        
        .notification-warning {
            border-left-color: #f59e0b;
            color: #92400e;
        }
        
        .notification i {
            font-size: 1.25rem;
        }
    `;
    
    const styleSheet = document.createElement('style');
    styleSheet.textContent = notificationStyles;
    document.head.appendChild(styleSheet);
});
