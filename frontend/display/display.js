let ws;
const storiesContainer = document.getElementById('stories-container');
const totalStoriesCounter = document.getElementById('total-stories');

function createParticles() {
    const particlesContainer = document.getElementById('particles');
    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 15 + 's';
        particlesContainer.appendChild(particle);
    }
}

let heartbeatTimer;

function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${window.location.host}/ws/display`);
    
    ws.onopen = () => { 
        console.log('✅ Display WebSocket connected'); 
        loadApprovedStories(); 

        clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                try { ws.send('ping'); } catch (e) { /* no-op */ }
            }
        }, 25000);
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        console.log('📨 WebSocket message:', message);
        if (message.type === 'new_story') {
            console.log('🎉 New story with emoji theme:', message.data.emoji_theme_data);
            addStoryCard(message.data, true);
            updateStatsCounter();
        }
    };
    
    ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
    };
    
    ws.onclose = (ev) => {
        console.log('🔌 WebSocket disconnected, reconnecting...', { code: ev.code, reason: ev.reason });
        clearInterval(heartbeatTimer);
        setTimeout(connectWebSocket, 3000);
    };
}

async function loadApprovedStories() {
    console.log('📚 Loading approved stories...');
    try {
        const response = await fetch('/api/stories?limit=20');
        const stories = await response.json();
        
        console.log('📖 Loaded stories:', stories.length, stories);
        
        storiesContainer.innerHTML = '';
        
        if (stories.length === 0) {
            console.log('📭 No stories to display');
            storiesContainer.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">💜</div>
                    <h2>Καλώς ήρθατε! 🌟</h2>
                    <p>Οι ιστορίες σας θα εμφανιστούν εδώ... ✨</p>
                    <div class="welcome-emoji">🎯 💪 🌈 🎉</div>
                </div>
            `;
        } else {
            console.log('✨ Displaying', stories.length, 'stories');
            stories.reverse().forEach((story, index) => {
                console.log(`Adding story ${index + 1}:`, story);
                addStoryCard(story, false);
            });
        }
        
        updateStatsCounter();
    } catch (error) {
        console.error('❌ Error loading stories:', error);
    }
}

function addStoryCard(story, animate = true) {
    console.log('➕ Adding story card:', story);
    
    const welcomeMsg = storiesContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        console.log('🗑️ Removing welcome message');
        welcomeMsg.remove();
    }

    const card = document.createElement('div');
    card.className = 'story-card';
    if (!animate) {
        card.style.animation = 'none';
        card.style.opacity = '1';
    }
    
    const createdDate = new Date(story.created_at);
    const timeStr = createdDate.toLocaleTimeString('el-GR', { hour: '2-digit', minute: '2-digit' });
    
    const authorName = story.author_name || story.author || 'Ανώνυμος';
    const storyText = story.transformed_text || story.text || 'Κείμενο μη διαθέσιμο';
    const llmComment = story.llm_comment || '';
    
    // Get emoji theme data
    let emojiDisplay = '';
    if (story.emoji_theme_data) {
        const emojis = story.emoji_theme_data.emojis || ['💜', '✨'];
        const animation = story.emoji_theme_data.animation || 'float';
        const color = story.emoji_theme_data.color || 'purple';
        
        emojiDisplay = `
            <div class="story-emojis ${animation}" data-color="${color}">
                ${emojis.slice(0, 3).map(emoji => `<span class="emoji">${emoji}</span>`).join('')}
            </div>
        `;
    }
    
    // Comment display
    let commentDisplay = '';
    if (llmComment && llmComment.trim()) {
        commentDisplay = `
            <div class="llm-comment-section">
                <p class="comment-label">💬 Σχόλιο:</p>
                <p class="comment-text">${llmComment}</p>
            </div>
        `;
    }
    
    card.innerHTML = `
        <div class="story-header">
            <div class="story-author">${authorName}</div>
            <div class="story-time">${timeStr}</div>
        </div>
        ${emojiDisplay}
        <div class="story-text">${storyText}</div>
        ${commentDisplay}
    `;
    
    storiesContainer.insertBefore(card, storiesContainer.firstChild);
    console.log('✅ Story card added to DOM');
    
    const allCards = storiesContainer.querySelectorAll('.story-card');
    if (allCards.length > 20) {
        allCards[allCards.length - 1].remove();
        console.log('🗑️ Removed oldest story (max 20)');
    }
}

async function updateStatsCounter() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        console.log('📊 Stats:', stats);
        totalStoriesCounter.textContent = stats.approved;
    } catch (error) {
        console.error('❌ Error updating stats:', error);
    }
}

console.log('🚀 Initializing display page...');
createParticles();
connectWebSocket();
setInterval(updateStatsCounter, 30000);
