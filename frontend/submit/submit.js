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
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        alert('Δεν ήταν δυνατή η πρόσβαση στο μικρόφωνο.');
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
        alert('Παρακαλώ γράψτε ή ηχογραφήστε την ιστορία σας');
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
        
        if (!response.ok) throw new Error('Submission failed');
        
        const data = await response.json();
        
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
        
        transformedPreview.innerHTML = `
            <div class="transformed-story">
                <p class="label">Η μετασχηματισμένη ιστορία σας:</p>
                ${emojiDisplay}
                <p class="story-text">"${data.transformed_text}"</p>
                ${authorName ? `<p class="author">- ${authorName}</p>` : ''}
            </div>
        `;
        
        formContainer.classList.add('hidden');
        successContainer.classList.remove('hidden');
    } catch (err) {
        alert('Σφάλμα υποβολής.');
        submitBtn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
    }
});
