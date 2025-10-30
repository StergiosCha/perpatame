let ws;
let moderatorName = localStorage.getItem('moderatorName') || '';
const moderatorInput = document.getElementById('moderator-name');
const pendingQueue = document.getElementById('pending-queue');
const statusDot = document.getElementById('status-dot');
const connectionStatus = document.getElementById('connection-status');

moderatorInput.value = moderatorName;

moderatorInput.addEventListener('change', (e) => {
    moderatorName = e.target.value.trim();
    localStorage.setItem('moderatorName', moderatorName);
});

function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${window.location.host}/ws/moderate`);
    
    ws.onopen = () => {
        console.log('🛡️ Moderator WebSocket connected');
        statusDot.classList.remove('disconnected');
        connectionStatus.textContent = 'Συνδεδεμένο';
        loadPendingStories();
        loadStats();
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'new_submission') {
            console.log('📝 New submission received:', message.data);
            addStoryCard(message.data);
            loadStats();
            showNotification('Νέα ιστορία προς έγκριση!', 'success');
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        statusDot.classList.add('disconnected');
        connectionStatus.textContent = 'Αποσυνδεδεμένο';
        setTimeout(connectWebSocket, 3000);
    };
}

async function loadPendingStories() {
    try {
        const response = await fetch('/api/stories/pending');
        const stories = await response.json();
        
        pendingQueue.innerHTML = '';
        
        if (stories.length === 0) {
            pendingQueue.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3>Δεν υπάρχουν εκκρεμείς ιστορίες</h3>
                    <p>Νέες υποβολές θα εμφανιστούν εδώ αυτόματα</p>
                </div>
            `;
        } else {
            stories.forEach(story => addStoryCard(story));
        }
    } catch (error) {
        console.error('Error loading pending stories:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        document.getElementById('stat-pending').textContent = stats.pending;
        document.getElementById('stat-approved').textContent = stats.approved;
        document.getElementById('stat-rejected').textContent = stats.rejected;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function addStoryCard(story) {
    const emptyState = pendingQueue.querySelector('.empty-state');
    if (emptyState) {
        pendingQueue.innerHTML = '';
    }

    const card = document.createElement('div');
    card.className = 'story-card';
    card.id = `story-${story.id}`;
    
    const createdDate = new Date(story.created_at);
    const timeStr = createdDate.toLocaleString('el-GR');
    
    card.innerHTML = `
        <div class="story-meta">
            <span class="story-id">ID: ${story.id}</span>
            <span class="story-time">${timeStr}</span>
        </div>
        
        ${story.author ? `<div class="story-author">Από: ${story.author}</div>` : ''}
        
        <div class="story-section">
            <div class="story-section-title">Πρωτότυπο Κείμενο</div>
            <div class="story-text original">${story.original_text}</div>
        </div>
        
        <div class="story-section">
            <div class="story-section-title">Μετασχηματισμένο Κείμενο</div>
            <div class="story-text transformed">${story.transformed_text}</div>
        </div>
        
        <div class="action-buttons">
            <button class="btn btn-approve" onclick="moderateStory(${story.id}, 'approve')">
                ✓ Έγκριση
            </button>
            <button class="btn btn-reject" onclick="moderateStory(${story.id}, 'reject')">
                ✗ Απόρριψη
            </button>
        </div>
    `;
    
    pendingQueue.insertBefore(card, pendingQueue.firstChild);
}

async function moderateStory(storyId, action) {
    if (!moderatorName) {
        showNotification('Παρακαλώ εισάγετε το όνομά σας πρώτα', 'error');
        moderatorInput.focus();
        return;
    }

    const card = document.getElementById(`story-${storyId}`);
    const buttons = card.querySelectorAll('.btn');
    buttons.forEach(btn => btn.disabled = true);
    
    try {
        const response = await fetch('/api/moderate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                story_id: storyId,
                action: action,
                moderator_name: moderatorName
            })
        });
        
        if (!response.ok) throw new Error('Moderation failed');
        
        card.style.opacity = '0';
        card.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            card.remove();
            
            if (pendingQueue.children.length === 0) {
                pendingQueue.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <h3>Δεν υπάρχουν εκκρεμείς ιστορίες</h3>
                        <p>Νέες υποβολές θα εμφανιστούν εδώ αυτόματα</p>
                    </div>
                `;
            }
        }, 300);
        
        const actionText = action === 'approve' ? 'εγκρίθηκε' : 'απορρίφθηκε';
        showNotification(`Η ιστορία ${actionText} επιτυχώς`, 'success');
        
        loadStats();
        
    } catch (error) {
        console.error('Moderation error:', error);
        showNotification('Σφάλμα κατά την επεξεργασία', 'error');
        buttons.forEach(btn => btn.disabled = false);
    }
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

connectWebSocket();