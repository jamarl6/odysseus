import * as Modals from './modalManager.js';

let coachSessionId = null;
let isStreaming = false;

const chatContainer = document.getElementById('fitnesscoach-chat-container');
const chatInput = document.getElementById('fitnesscoach-input');
const sendBtn = document.getElementById('fitnesscoach-send-btn');

async function getCoachSession() {
    if (coachSessionId) return coachSessionId;
    try {
        const r = await fetch('/api/fitnesscoach/session');
        if (!r.ok) throw new Error("Failed to init session");
        const data = await r.json();
        coachSessionId = data.session_id;
        return coachSessionId;
    } catch (e) {
        console.error('Failed to get coach session', e);
        return null;
    }
}

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.style.marginBottom = '15px';
    msgDiv.style.padding = '10px 15px';
    msgDiv.style.borderRadius = '8px';
    msgDiv.style.maxWidth = '85%';
    
    if (role === 'user') {
        msgDiv.style.background = 'var(--user-bubble-bg)';
        msgDiv.style.alignSelf = 'flex-end';
        msgDiv.style.marginLeft = 'auto';
    } else {
        msgDiv.style.background = 'var(--ai-bubble-bg)';
        msgDiv.style.border = '1px solid var(--bubble-border)';
        msgDiv.style.alignSelf = 'flex-start';
        msgDiv.style.marginRight = 'auto';
    }
    
    msgDiv.innerHTML = content;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msgDiv;
}

async function sendMessage() {
    if (isStreaming) return;
    const text = chatInput.value.trim();
    if (!text) return;
    
    chatInput.value = '';
    appendMessage('user', text);
    
    const sid = await getCoachSession();
    if (!sid) {
        appendMessage('assistant', '<i>Error connecting to Fitness Coach.</i>');
        return;
    }

    isStreaming = true;
    sendBtn.disabled = true;
    
    const formData = new FormData();
    formData.append('message', text);
    formData.append('session_id', sid);
    formData.append('is_fitnesscoach', 'true');
    // Request agent mode explicitly (chat_routes will enforce this anyway)
    formData.append('mode', 'agent');
    
    const msgBubble = appendMessage('assistant', '<span class="typing-indicator">Coach denkt nach...</span>');
    let aiText = '';

    try {
        const res = await fetch('/api/chat_stream', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line
            
            for (let line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6).trim();
                    if (dataStr === '[DONE]') continue;
                    
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === 'token') {
                            aiText += data.text;
                            // Basic escaping for now; ideally we'd use markdown renderer
                            msgBubble.innerText = aiText;
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        } else if (data.type === 'error') {
                            aiText += `\n[Error: ${data.message}]`;
                            msgBubble.innerText = aiText;
                        }
                    } catch (e) {
                        // Ignore parse errors on partial chunks if any
                    }
                }
            }
        }
    } catch (e) {
        aiText += `\n[Verbindungsfehler: ${e.message}]`;
        msgBubble.innerText = aiText;
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

Modals.register('fitnesscoach-modal', {
    railBtnId: 'tool-fitnesscoach-btn',
    restoreFn: () => {
        getCoachSession(); // Prefetch on open
        if (chatContainer.children.length === 0) {
            appendMessage('assistant', 'Hallo! Ich bin dein persönlicher Fitness Coach. Wie kann ich dir heute helfen? Ich verwalte deine Ziele und Trainingspläne sicher in deinen lokalen Dateien.');
        }
        setTimeout(() => chatInput.focus(), 100);
    },
    closeFn: () => {}
});

document.getElementById('tool-fitnesscoach-btn').addEventListener('click', () => {
    Modals.toggle('fitnesscoach-modal');
});

document.getElementById('close-fitnesscoach-modal').addEventListener('click', () => {
    Modals.close('fitnesscoach-modal');
});
