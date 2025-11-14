let mediaRecorder;
let audioChunks = [];
let recordingStartTime;
let recordingInterval;
let currentInputMethod = 'text';

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.input-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        currentInputMethod = btn.dataset.method;
        document.getElementById(`${currentInputMethod}-input-panel`).classList.add('active');
    });
});

const textarea = document.getElementById('story-text');
const charCount = document.getElementById('char-count');
textarea.addEventListener('input', () => {
    const count = textarea.value.length;
    charCount.textContent = count;
    if (count > 500) {
        textarea.value = textarea.value.substring(0, 500);
        charCount.textContent = 500;
    }
});

const recordBtn = document.getElementById('record-btn');
const recordingStatus = document.getElementById('recording-status');
const transcriptionResult = document.getElementById('transcription-result');
const transcriptionText = document.getElementById('transcription-text');
const retryBtn = document.getElementById('retry-record');

recordBtn.addEventListener('click', async () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        stopRecording();
    } else {
        startRecording();
    }
});

retryBtn.addEventListener('click', () => {
    transcriptionResult.classList.add('hidden');
    recordBtn.classList.remove('hidden');
    audioChunks = [];
});

async function startRecording() {
    console.log('Starting recording...', {
        hasMediaDevices: !!navigator.mediaDevices,
        hasGetUserMedia: !!navigator.mediaDevices?.getUserMedia,
        protocol: window.location.protocol,
        host: window.location.host
    });

    // Get getUserMedia with fallback for older browsers
    const getUserMedia = navigator.mediaDevices?.getUserMedia 
        || navigator.getUserMedia 
        || navigator.webkitGetUserMedia 
        || navigator.mozGetUserMedia 
        || navigator.msGetUserMedia;

    if (!getUserMedia) {
        console.error('No getUserMedia support found');
        alert('Το browser σας δεν υποστηρίζει ηχογράφηση. Χρησιμοποιήστε Chrome, Firefox ή Safari.');
        return;
    }

    try {
        // Use modern API if available, otherwise legacy
        const stream = navigator.mediaDevices 
            ? await navigator.mediaDevices.getUserMedia({ audio: true })
            : await new Promise((resolve, reject) => {
                getUserMedia.call(navigator, { audio: true }, resolve, reject);
            });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await transcribeAudio(audioBlob);
            stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        recordBtn.classList.add('recording');
        recordBtn.querySelector('.record-text').textContent = 'Πατήστε για Διακοπή';
        recordingStatus.classList.remove('hidden');
        
        recordingStartTime = Date.now();
        recordingInterval = setInterval(updateRecordingTime, 100);
    } catch (err) {
        console.error('Microphone error:', err);
        let errorMsg = 'Δεν ήταν δυνατή η πρόσβαση στο μικρόφωνο.';
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            errorMsg = 'Παρακαλώ επιτρέψτε την πρόσβαση στο μικρόφωνο στις ρυθμίσεις του browser.';
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            errorMsg = 'Δεν βρέθηκε μικρόφωνο. Ελέγξτε τις συνδέσεις.';
        } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
            errorMsg = 'Το μικρόφωνο χρησιμοποιείται από άλλη εφαρμογή.';
        }
        alert(errorMsg);
        recordBtn.classList.remove('recording');
        recordingStatus.classList.add('hidden');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('.record-text').textContent = 'Πατήστε για Ηχογράφηση';
        recordingStatus.classList.add('hidden');
        clearInterval(recordingInterval);
    }
}

function updateRecordingTime() {
    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    document.getElementById('recording-time').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

async function transcribeAudio(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    
    try {
        const response = await fetch('/api/transcribe', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Transcription failed');
        
        const data = await response.json();
        transcriptionText.textContent = data.text;
        transcriptionResult.classList.remove('hidden');
        recordBtn.classList.add('hidden');
    } catch (err) {
        alert('Σφάλμα μεταγραφής.');
        recordBtn.classList.remove('hidden');
    }
}

const form = document.getElementById('story-form');
const submitBtn = document.getElementById('submit-btn');
const btnText = document.getElementById('btn-text');
const btnLoader = document.getElementById('btn-loader');
const formContainer = document.getElementById('form-container');
const successContainer = document.getElementById('success-container');
const transformedPreview = document.getElementById('transformed-preview');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    let storyText;
    if (currentInputMethod === 'text') {
        storyText = textarea.value.trim();
    } else {
        storyText = transcriptionText.textContent.trim();
    }
    
    if (!storyText || storyText.length < 10) {
        alert('Παρακαλώ γράψτε ή ηχογραφήστε την ιστορία/το σχόλιό σας');
        return;
    }
    
    const authorName = document.getElementById('author-name').value.trim();
    const transformationStyle = document.getElementById('transformation-style').value || null;
    
    submitBtn.disabled = true;
    btnText.classList.add('hidden');
    btnLoader.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: storyText,
                author_name: authorName || null,
                transformation_style: transformationStyle
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server error response:', errorText);
            let errorMessage = 'Submission failed';
            try {
                const errorData = JSON.parse(errorText);
                errorMessage = errorData.detail || errorData.error || errorMessage;
            } catch (e) {
                errorMessage = errorText || errorMessage;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        console.log('Submission successful:', data);
        
        // Add emoji display if available
        let emojiDisplay = '';
        if (data.emoji_theme && data.emoji_theme.emojis) {
            const emojis = data.emoji_theme.emojis.slice(0, 3);
            emojiDisplay = `
                <div class="preview-emojis">
                    ${emojis.map(emoji => `<span class="preview-emoji">${emoji}</span>`).join('')}
                </div>
            `;
        }
        
        let commentDisplay = '';
        if (data.llm_comment && data.llm_comment.trim()) {
            commentDisplay = `
                <div class="llm-comment-section">
                    <p class="comment-label">💬 Σχόλιο:</p>
                    <p class="comment-text">${data.llm_comment}</p>
                </div>
            `;
        }
        
        transformedPreview.innerHTML = `
            <div class="transformed-story">
                <p class="label">Η μετασχηματισμένη ιστορία/το σχόλιό σας:</p>
                ${emojiDisplay}
                <p class="story-text">"${data.transformed_text}"</p>
                ${authorName ? `<p class="author">- ${authorName}</p>` : ''}
                ${commentDisplay}
            </div>
        `;
        
        formContainer.classList.add('hidden');
        successContainer.classList.remove('hidden');
    } catch (err) {
        console.error('Submission error:', err);
        console.error('Error details:', err.message, err.stack);
        alert(`Σφάλμα υποβολής: ${err.message || 'Άγνωστο σφάλμα'}`);
        submitBtn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
    }
});
