from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import google.generativeai as genai
from datetime import datetime
import sqlite3
import os
import tempfile
import speech_recognition as sr
from pydub import AudioSegment
import json

app = FastAPI(title="Story Transformer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="../frontend/assets"), name="assets")
app.mount("/submit", StaticFiles(directory="../frontend/submit", html=True), name="submit")
app.mount("/display", StaticFiles(directory="../frontend/display", html=True), name="display")
app.mount("/moderate", StaticFiles(directory="../frontend/moderate", html=True), name="moderate")

def get_db():
    conn = sqlite3.connect('stories.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT NOT NULL,
            transformed_text TEXT,
            author_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            moderated_at TIMESTAMP,
            moderated_by TEXT,
            emoji_theme TEXT,
            emoji_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Enhanced AI Generation Features
class StoryTransformer:
    def __init__(self):
        self.prompts = {
            'inspirational': """Μετέτρεψε αυτή την προσωπική ιστορία σε ένα εμπνευσμένο, 
συναισθηματικό μήνυμα 2-3 προτάσεων στα Ελληνικά. 
Εστίασε στην ελπίδα, τη δύναμη και την αντοχή. Κράτησε το συναίσθημα, κάνε το αισιόδοξο, 
διατήρησε την ανθρώπινη φωνή, αλλά χωρίς υπερβολές.

ΣΗΜΑΝΤΙΚΟ: Αυτή είναι μια εφαρμογή για ιστορίες σχετικές με την Πολλαπλή Σκλήρυνση και την υγεία. 
Αν το κείμενο είναι ΞΕΚΑΘΑΡΑ άσχετο (π.χ. πολιτικά νέα, οικονομικά, τεχνικά θέματα), 
επέστρεψε: "Το κείμενο δεν είναι κατάλληλο για μετασχηματισμό. Παρακαλώ εισάγετε μια προσωπική ιστορία."

Αλλιώς, μετασχημάτισε το κείμενο σε εμπνευσμένο μήνυμα.

Πρωτότυπο κείμενο: {text}

Μετασχηματισμένο μήνυμα:""",
            
            'emotional': """Μετέτρεψε αυτή την προσωπική ιστορία σε ένα συναισθηματικό, 
εγκάρδιο μήνυμα 2-3 προτάσεων στα Ελληνικά.
Εστίασε στο συναίσθημα, την ανθρώπινη εμπειρία και τη συμπαράσταση. 
Διατήρησε την αυθεντικότητα και την ευαισθησία.

ΣΗΜΑΝΤΙΚΟ: Αυτή είναι μια εφαρμογή για ιστορίες σχετικές με την Πολλαπλή Σκλήρυνση και την υγεία. 
Αν το κείμενο είναι ΞΕΚΑΘΑΡΑ άσχετο (π.χ. πολιτικά νέα, οικονομικά, τεχνικά θέματα), 
επέστρεψε: "Το κείμενο δεν είναι κατάλληλο για μετασχηματισμό. Παρακαλώ εισάγετε μια προσωπική ιστορία."

Αλλιώς, μετασχημάτισε το κείμενο σε συναισθηματικό μήνυμα.

Πρωτότυπο κείμενο: {text}

Μετασχηματισμένο μήνυμα:""",
            
            'community': """Μετέτρεψε αυτή την προσωπική ιστορία σε ένα μήνυμα 
κοινότητας και αλληλεγγύης 2-3 προτάσεων στα Ελληνικά.
Εστίασε στη δύναμη της κοινότητας, την αλληλεγγύη και το ότι δεν είμαστε μόνοι.

ΣΗΜΑΝΤΙΚΟ: Αυτή είναι μια εφαρμογή για ιστορίες σχετικές με την Πολλαπλή Σκλήρυνση και την υγεία. 
Αν το κείμενο είναι ΞΕΚΑΘΑΡΑ άσχετο (π.χ. πολιτικά νέα, οικονομικά, τεχνικά θέματα), 
επέστρεψε: "Το κείμενο δεν είναι κατάλληλο για μετασχηματισμό. Παρακαλώ εισάγετε μια προσωπική ιστορία."

Αλλιώς, μετασχημάτισε το κείμενο σε μήνυμα κοινότητας.

Πρωτότυπο κείμενο: {text}

Μετασχηματισμένο μήνυμα:""",
            
            'resilience': """Μετέτρεψε αυτή την προσωπική ιστορία σε ένα μήνυμα 
αντοχής και δύναμης 2-3 προτάσεων στα Ελληνικά.
Εστίασε στην αντοχή, τη δύναμη του ανθρώπινου πνεύματος και την ικανότητα να ξεπερνάμε τις δυσκολίες.

ΣΗΜΑΝΤΙΚΟ: Αυτή είναι μια εφαρμογή για ιστορίες σχετικές με την Πολλαπλή Σκλήρυνση και την υγεία. 
Αν το κείμενο είναι ΞΕΚΑΘΑΡΑ άσχετο (π.χ. πολιτικά νέα, οικονομικά, τεχνικά θέματα), 
επέστρεψε: "Το κείμενο δεν είναι κατάλληλο για μετασχηματισμό. Παρακαλώ εισάγετε μια προσωπική ιστορία."

Αλλιώς, μετασχημάτισε το κείμενο σε μήνυμα αντοχής.

Πρωτότυπο κείμενο: {text}

Μετασχηματισμένο μήνυμα:"""
        }
    
    def is_relevant_content(self, text: str) -> bool:
        """Check if text is relevant for MS story transformation"""
        # Only reject CLEARLY irrelevant content (news, politics, technical stuff)
        irrelevant_keywords = [
            'βουλή', 'βουλής', 'κυβέρνηση', 'υπουργός', 'πρωθυπουργός',
            'εξεταστική', 'επιτροπή', 'σκάνδαλο', 'οπεκεπε',
            'εκλογές', 'κόμμα', 'ψήφισμα', 'νομοσχέδιο',
            'χρηματιστήριο', 'μετοχές', 'nasdaq', 'κατάθεση'
        ]
        
        text_lower = text.lower()
        
        # Count irrelevant keywords
        irrelevant_count = sum(1 for keyword in irrelevant_keywords if keyword in text_lower)
        
        # Only reject if text has MANY irrelevant keywords (clearly politics/news/business)
        # This is much more permissive - allows most personal stories through
        if irrelevant_count >= 3:
            return False
        
        # Accept everything else - let the AI decide if it's appropriate
        return True
    
    def get_emoji_theme(self, text: str) -> dict:
        """Get emoji theme based on story content"""
        # Simple keyword-based emoji selection
        text_lower = text.lower()
        
        # Strength/Resilience themes
        if any(word in text_lower for word in ['δυνατή', 'δυνατός', 'αντοχή', 'δύναμη', 'παλεύω', 'δεν τα παρατάω']):
            return {
                "theme": "strength",
                "emojis": ["💪", "🔥", "⚡", "🏋️‍♀️", "💎"],
                "color": "orange",
                "animation": "bounce"
            }
        
        # Love/Family themes
        elif any(word in text_lower for word in ['αγάπη', 'οικογένεια', 'υποστήριξη', 'μαμά', 'μπαμπάς', 'παιδιά']):
            return {
                "theme": "love",
                "emojis": ["💝", "💕", "🌈", "🦋", "💖"],
                "color": "pink",
                "animation": "float"
            }
        
        # Community themes
        elif any(word in text_lower for word in ['μαζί', 'κοινότητα', 'φίλοι', 'υποστήριξη', 'αλληλεγγύη']):
            return {
                "theme": "community",
                "emojis": ["🤝", "👥", "🌟", "💜", "🎯"],
                "color": "blue",
                "animation": "pulse"
            }
        
        # Medical/Health themes
        elif any(word in text_lower for word in ['γιατρός', 'θεραπεία', 'φάρμακο', 'νοσοκομείο', 'υγεία']):
            return {
                "theme": "medical",
                "emojis": ["🏥", "⚕️", "💊", "🩺", "🌱"],
                "color": "green",
                "animation": "glow"
            }
        
        # Success/Achievement themes
        elif any(word in text_lower for word in ['επιτυχία', 'κέρδισα', 'κατάφερα', 'νίκη', 'πρόοδος']):
            return {
                "theme": "success",
                "emojis": ["🎉", "🏆", "✨", "🌟", "🎯"],
                "color": "gold",
                "animation": "sparkle"
            }
        
        # Default hope theme
        else:
            return {
                "theme": "hope",
                "emojis": ["🌟", "💜", "✨", "🌈", "🦋"],
                "color": "purple",
                "animation": "float"
            }
    
    def analyze_story(self, text: str) -> dict:
        """Analyze story to determine best transformation approach"""
        # First check if content is relevant
        if not self.is_relevant_content(text):
            return {
                "emotional_tone": "irrelevant",
                "main_themes": ["irrelevant"],
                "suggested_style": "inspirational",
                "confidence": 0.1,
                "is_relevant": False
            }
        
        analysis_prompt = f"""Ανάλυσε αυτό το κείμενο και επέστρεψε JSON με:
- emotional_tone: "positive", "neutral", "challenging", "hopeful"
- main_themes: ["struggle", "hope", "family", "medical", "community", "achievement"]
- suggested_style: "inspirational", "emotional", "community", "resilience"
- confidence: 0-1

Κείμενο: {text[:200]}..."""
        
        try:
            response = model.generate_content(analysis_prompt)
            # Try to parse JSON response
            try:
                result = json.loads(response.text)
                result['is_relevant'] = True
                return result
            except:
                # Fallback if JSON parsing fails
                return {
                    "emotional_tone": "hopeful",
                    "main_themes": ["struggle", "hope"],
                    "suggested_style": "inspirational",
                    "confidence": 0.8,
                    "is_relevant": True
                }
        except Exception as e:
            print(f"⚠️ Story analysis failed: {e}")
            return {
                "emotional_tone": "neutral",
                "main_themes": ["struggle"],
                "suggested_style": "inspirational", 
                "confidence": 0.5,
                "is_relevant": True
            }
    
    def generate_enhanced(self, text: str, style: str = None) -> dict:
        """Generate enhanced transformation with quality metrics"""
        analysis = self.analyze_story(text)
        
        # Check if content is relevant
        if not analysis.get("is_relevant", True):
            return {
                "transformed_text": "❌ Το κείμενο δεν είναι κατάλληλο για μετασχηματισμό. Παρακαλώ εισάγετε μια προσωπική ιστορία σχετική με την Πολλαπλή Σκλήρυνση ή θέματα υγείας.",
                "style_used": "none",
                "quality_score": 0.0,
                "analysis": analysis,
                "success": False,
                "error": "Irrelevant content"
            }
        
        # Choose style based on analysis or user preference
        if not style:
            style = analysis["suggested_style"]
        
        prompt = self.prompts.get(style, self.prompts['inspirational'])
        formatted_prompt = prompt.format(text=text)
        
        try:
            response = model.generate_content(formatted_prompt)
            transformed = response.text.strip()
            
            # Check if AI refused to transform
            if "δεν είναι κατάλληλο" in transformed.lower():
                return {
                    "transformed_text": transformed,
                    "style_used": style,
                    "quality_score": 0.0,
                    "analysis": analysis,
                    "success": False,
                    "error": "AI rejected transformation"
                }
            
            # Quality metrics
            quality_score = self.assess_quality(text, transformed)
            
            return {
                "transformed_text": transformed,
                "style_used": style,
                "quality_score": quality_score,
                "analysis": analysis,
                "success": True
            }
        except Exception as e:
            print(f"❌ Transformation failed: {e}")
            # Fallback to original text
            return {
                "transformed_text": "⚠️ Σφάλμα μετασχηματισμού. Παρακαλώ δοκιμάστε ξανά.",
                "style_used": "fallback",
                "quality_score": 0.0,
                "analysis": analysis,
                "success": False,
                "error": str(e)
            }
    
    def assess_quality(self, original: str, transformed: str) -> float:
        """Assess quality of transformation (0-1)"""
        # Simple quality metrics
        length_ratio = len(transformed) / max(len(original), 1)
        has_emotion = any(word in transformed.lower() for word in ['ελπίδα', 'δύναμη', 'αντοχή', 'αγάπη', 'υποστήριξη'])
        is_appropriate_length = 50 <= len(transformed) <= 300
        
        score = 0.0
        if 0.3 <= length_ratio <= 1.5:  # Reasonable length ratio
            score += 0.3
        if has_emotion:
            score += 0.4
        if is_appropriate_length:
            score += 0.3
            
        return min(score, 1.0)

transformer = StoryTransformer()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.moderator_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket, is_moderator: bool = False):
        await websocket.accept()
        if is_moderator:
            self.moderator_connections.append(websocket)
        else:
            self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket, is_moderator: bool = False):
        if is_moderator:
            if websocket in self.moderator_connections:
                self.moderator_connections.remove(websocket)
        else:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"⚠️ Broadcast error: {e}")
                pass
    
    async def notify_moderators(self, message: dict):
        for connection in self.moderator_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"⚠️ Moderator notification error: {e}")
                pass

manager = ConnectionManager()

class StorySubmission(BaseModel):
    text: str
    author_name: Optional[str] = None
    transformation_style: Optional[str] = None

class ModerationAction(BaseModel):
    story_id: int
    action: str
    moderator_name: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(None), file: UploadFile = File(None)):
    """Transcribe audio to text using speech recognition"""
    tmp_original = None
    tmp_wav = None
    
    try:
        # Pick whichever field name the client used (audio or file)
        upload = audio or file
        if upload is None:
            raise HTTPException(status_code=400, detail="Δεν βρέθηκε αρχείο ήχου (πεδίο 'audio').")

        # Save uploaded file
        file_ext = os.path.splitext(upload.filename)[1].lower() or '.webm'
        tmp_original = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        tmp_original.write(await upload.read())
        tmp_original.close()
        
        # Convert to WAV if needed
        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name
        audio_segment = AudioSegment.from_file(tmp_original.name)
        
        if file_ext != '.wav':
            audio_segment.export(tmp_wav, format="wav")
        else:
            tmp_wav = tmp_original.name
        
        # Check duration
        with sr.AudioFile(tmp_wav) as source:
            if source.DURATION < 0.5:
                raise HTTPException(status_code=400, detail="Η ηχογράφηση είναι πολύ σύντομη.")
        
        # Configure recognizer
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8
        
        # Transcribe
        with sr.AudioFile(tmp_wav) as source:
            recognizer.adjust_for_ambient_noise(source, duration=min(1.0, source.DURATION / 2))
            audio_data = recognizer.record(source)
        
        text = None
        try:
            text = recognizer.recognize_google(audio_data, language='el-GR', show_all=False)
        except sr.UnknownValueError:
            try:
                text = recognizer.recognize_google(audio_data, language='en-US', show_all=False)
            except sr.UnknownValueError:
                try:
                    text = recognizer.recognize_google(audio_data, language='el', show_all=False)
                except sr.UnknownValueError:
                    raise sr.UnknownValueError("Could not understand audio")
        
        # Cleanup
        if tmp_original and os.path.exists(tmp_original.name):
            os.unlink(tmp_original.name)
        if tmp_wav and os.path.exists(tmp_wav) and tmp_wav != tmp_original.name:
            os.unlink(tmp_wav)
        
        if not text:
            raise sr.UnknownValueError("No text recognized")
        
        return {"text": text}
        
    except sr.UnknownValueError:
        if tmp_original and os.path.exists(tmp_original.name):
            os.unlink(tmp_original.name)
        if tmp_wav and os.path.exists(tmp_wav):
            os.unlink(tmp_wav)
        raise HTTPException(status_code=400, detail="Δεν κατάλαβα τι είπατε.")
    except Exception as e:
        if tmp_original and os.path.exists(tmp_original.name):
            os.unlink(tmp_original.name)
        if tmp_wav and os.path.exists(tmp_wav):
            os.unlink(tmp_wav)
        print(f"❌ Transcription error: {e}")
        raise HTTPException(status_code=500, detail="Σφάλμα μεταγραφής.")

@app.post("/api/submit")
async def submit_story(submission: StorySubmission):
    if not submission.text or len(submission.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Το κείμενο είναι πολύ σύντομο (τουλάχιστον 10 χαρακτήρες)")
    
    # Use enhanced transformer with user preference
    try:
        result = transformer.generate_enhanced(submission.text, submission.transformation_style)
        transformed = result["transformed_text"]
        quality_score = result["quality_score"]
        style_used = result["style_used"]
        
        # Log quality metrics for monitoring
        print(f"📊 Story transformation - Style: {style_used}, Quality: {quality_score:.2f}, Success: {result['success']}")
        
        # Don't save if transformation failed or content was irrelevant
        if not result["success"]:
            return {
                "success": False,
                "error": transformed,
                "transformed_text": transformed,
                "status": "rejected"
            }
        
    except Exception as e:
        print(f"❌ Enhanced transformation failed: {e}")
        raise HTTPException(status_code=500, detail="Σφάλμα μετασχηματισμού. Παρακαλώ δοκιμάστε ξανά.")
    
    # Save to database
    try:
        conn = get_db()
        
        # Get emoji theme
        emoji_theme = transformer.get_emoji_theme(submission.text)
        emoji_data_json = json.dumps(emoji_theme)
        
        cursor = conn.execute(
            "INSERT INTO stories (original_text, transformed_text, author_name, status, emoji_theme, emoji_data) VALUES (?, ?, ?, 'pending', ?, ?)",
            (submission.text, transformed, submission.author_name, emoji_theme['theme'], emoji_data_json)
        )
        story_id = cursor.lastrowid
        conn.commit()
        
        story = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        conn.close()
        
        # Notify moderators
        await manager.notify_moderators({
            "type": "new_submission",
            "data": {
                "id": story["id"],
                "original_text": story["original_text"],
                "transformed_text": story["transformed_text"],
                "author": story["author_name"],
                "created_at": story["created_at"]
            }
        })
        
        return {
            "success": True, 
            "id": story_id, 
            "transformed_text": transformed,
            "status": "pending_moderation",
            "emoji_theme": emoji_theme
        }
    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(status_code=500, detail="Σφάλμα αποθήκευσης. Παρακαλώ δοκιμάστε ξανά.")

@app.get("/api/stories")
async def get_stories(limit: int = 50):
    conn = get_db()
    stories = conn.execute(
        "SELECT id, transformed_text, author_name, created_at, emoji_theme, emoji_data FROM stories WHERE status = 'approved' ORDER BY moderated_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    
    # Parse emoji data for each story
    result = []
    for story in stories:
        story_dict = dict(story)
        if story_dict['emoji_data']:
            try:
                story_dict['emoji_theme_data'] = json.loads(story_dict['emoji_data'])
            except:
                story_dict['emoji_theme_data'] = None
        result.append(story_dict)
    
    return result

@app.get("/api/stories/pending")
async def get_pending_stories():
    conn = get_db()
    stories = conn.execute(
        "SELECT id, original_text, transformed_text, author_name, created_at FROM stories WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in stories]

@app.post("/api/moderate")
async def moderate_story(action: ModerationAction):
    if action.action not in ['approve', 'reject']:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    conn = get_db()
    story = conn.execute("SELECT * FROM stories WHERE id = ?", (action.story_id,)).fetchone()
    
    if not story:
        conn.close()
        raise HTTPException(status_code=404, detail="Story not found")
    
    new_status = 'approved' if action.action == 'approve' else 'rejected'
    
    conn.execute(
        "UPDATE stories SET status = ?, moderated_at = CURRENT_TIMESTAMP, moderated_by = ? WHERE id = ?",
        (new_status, action.moderator_name, action.story_id)
    )
    conn.commit()
    
    updated_story = conn.execute("SELECT * FROM stories WHERE id = ?", (action.story_id,)).fetchone()
    conn.close()
    
    if action.action == 'approve':
        # Get emoji data for the story
        emoji_data = None
        if updated_story["emoji_data"]:
            try:
                emoji_data = json.loads(updated_story["emoji_data"])
            except:
                pass
        
        await manager.broadcast({
            "type": "new_story",
            "data": {
                "id": updated_story["id"],
                "text": updated_story["transformed_text"],
                "author": updated_story["author_name"],
                "created_at": updated_story["created_at"],
                "emoji_theme_data": emoji_data
            }
        })
    
    return {"success": True, "action": action.action}

@app.get("/api/stats")
async def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as count FROM stories").fetchone()["count"]
    approved = conn.execute("SELECT COUNT(*) as count FROM stories WHERE status = 'approved'").fetchone()["count"]
    pending = conn.execute("SELECT COUNT(*) as count FROM stories WHERE status = 'pending'").fetchone()["count"]
    rejected = conn.execute("SELECT COUNT(*) as count FROM stories WHERE status = 'rejected'").fetchone()["count"]
    conn.close()
    
    return {
        "total_submissions": total,
        "approved": approved,
        "pending": pending,
        "rejected": rejected
    }

@app.get("/api/transformation-styles")
async def get_transformation_styles():
    """Get available transformation styles"""
    return {
        "styles": [
            {
                "id": "inspirational",
                "name": "Εμπνευσμένο",
                "description": "Εστιάζει στην ελπίδα και τη δύναμη"
            },
            {
                "id": "emotional", 
                "name": "Συναισθηματικό",
                "description": "Εστιάζει στο συναίσθημα και την ανθρώπινη εμπειρία"
            },
            {
                "id": "community",
                "name": "Κοινότητα", 
                "description": "Εστιάζει στην αλληλεγγύη και τη συμπαράσταση"
            },
            {
                "id": "resilience",
                "name": "Αντοχή",
                "description": "Εστιάζει στην αντοχή και τη δύναμη του πνεύματος"
            }
        ]
    }

@app.post("/api/preview-transformation")
async def preview_transformation(submission: StorySubmission):
    """Preview transformation without saving"""
    if not submission.text or len(submission.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Το κείμενο είναι πολύ σύντομο")
    
    try:
        result = transformer.generate_enhanced(submission.text, submission.transformation_style)
        return {
            "transformed_text": result["transformed_text"],
            "style_used": result["style_used"],
            "quality_score": result["quality_score"],
            "analysis": result["analysis"],
            "success": result["success"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transformation failed: {str(e)}")

@app.websocket("/ws/display")
async def websocket_display(websocket: WebSocket):
    await manager.connect(websocket, is_moderator=False)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, is_moderator=False)

@app.websocket("/ws/moderate")
async def websocket_moderate(websocket: WebSocket):
    await manager.connect(websocket, is_moderator=True)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, is_moderator=True)

@app.get("/")
async def root():
    return {
        "message": "Story Transformer API - Powered by SimasiaAI",
        "endpoints": {
            "submit_page": "/submit",
            "display_page": "/display",
            "moderate_page": "/moderate",
            "api_docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)