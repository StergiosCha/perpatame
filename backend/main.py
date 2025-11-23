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
import re
from pathlib import Path

app = FastAPI(title="Story Transformer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

app.mount("/submit", StaticFiles(directory=str(FRONTEND_DIR / "submit"), html=True), name="submit")
app.mount("/display", StaticFiles(directory=str(FRONTEND_DIR / "display"), html=True), name="display")
app.mount("/moderate", StaticFiles(directory=str(FRONTEND_DIR / "moderate"), html=True), name="moderate")

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
            llm_comment TEXT,
            author_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            moderated_at TIMESTAMP,
            moderated_by TEXT,
            emoji_theme TEXT,
            emoji_data TEXT
        )
    ''')
    
    # Add llm_comment column if it doesn't exist (migration for existing databases)
    try:
        # Check if column exists by trying to select it
        conn.execute('SELECT llm_comment FROM stories LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        try:
            conn.execute('ALTER TABLE stories ADD COLUMN llm_comment TEXT')
            conn.commit()
            print("✅ Added llm_comment column to stories table")
        except sqlite3.OperationalError as e:
            print(f"⚠️ Could not add llm_comment column: {e}")
    
    conn.close()

# Configure Gemini with fallback models (from MEDEA paper branch)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model fallback chain (best to worst) - NO experimental models
MODEL_NAMES = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
]

# Initialize models
models = []
for model_name in MODEL_NAMES:
    try:
        m = genai.GenerativeModel(model_name)
        models.append((model_name, m))
        print(f"✅ Loaded model: {model_name}")
    except Exception as e:
        print(f"⚠️ Failed to load model {model_name}: {e}")

if not models:
    print("❌ ERROR: No Gemini models could be loaded!")
else:
    print(f"✅ Initialized with {len(models)} models")

def generate_with_fallback(prompt: str, temperature: float = 0.2, max_tokens: int = 1024) -> str:
    """Generate content with automatic model fallbacks"""
    if not models:
        raise Exception("No models available for generation")
    
    last_error = None
    
    # Try each model in the fallback chain
    for model_name, model in models:
        for attempt in range(3):  # 3 retries per model
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )
                
                if response.text and response.text.strip():
                    print(f"✅ Success with {model_name}")
                    return response.text.strip()
                else:
                    print(f"⚠️ Empty response from {model_name}")
                    continue
                    
            except Exception as e:
                print(f"⚠️ {model_name} attempt {attempt + 1} failed: {e}")
                last_error = e
                continue
    
    # All models failed
    raise Exception(f"All LLM models failed. Last error: {last_error}")

# Enhanced AI Generation Features
class StoryTransformer:
    def __init__(self):
        self.prompts = {
            'inspirational': """ΕΠΕΞΕΡΓΑΣΙΑ ΚΕΙΜΕΝΟΥ - ΔΥΟ ΜΕΡΗ

ΜΕΡΟΣ 1: ΕΛΑΦΡΥ EDITING
Κάνε ΜΟΝΟ ορθογραφικές/γραμματικές διορθώσεις. ΚΡΑΤΑ ΑΚΡΙΒΩΣ το ύφος, τη φωνή και όλες τις λέξεις. Αν δεν υπάρχουν λάθη, επέστρεψε το ΑΚΡΙΒΩΣ όπως είναι.

ΜΕΡΟΣ 2: ΣΧΟΛΙΟ (ΠΑΝΤΑ) - ΠΟΛΥ ΕΝΣΥΝΑΙΣΘΗΤΙΚΟ ΚΑΙ ΠΡΟΣΕΚΤΙΚΟ
Διάβασε προσεκτικά το κείμενο. Νιώσε το βάθος της εμπειρίας. Απάντησε με ένα σύντομο σχόλιο (1-2 προτάσεις) που:
- Δείχνει ΑΥΘΕΝΤΙΚΗ ενσυναίσθηση (όχι επιφανειακή)
- Αν το κείμενο έχει ήδη δύναμη και αντοχή, αναγνώρισε τη δύναμη και την αντοχή που φαίνεται
- Αν το κείμενο ΔΕΝ έχει δύναμη και αντοχή, προσδίδει ελπίδα και δύναμη με ΜΕΤΡΗΜΕΝΟ και σεβαστό τρόπο - όχι επιφανειακά, όχι false optimism, αλλά με αυθεντικότητα
- Είναι ΠΟΛΥ προσεκτικό με τα συναισθήματα - μην υποτιμάς, μην υπερβάλλεις
- Μπορεί να συνδέσει με προηγούμενες ιστορίες αν υπάρχει φυσική σύνδεση (π.χ. "Όπως και άλλοι στην κοινότητα μας που μοιράστηκαν παρόμοιες εμπειρίες...")
- ΧΩΡΙΣ condescension, χωρίς "θα δεις", "θα καταλάβεις", χωρίς να υποτιμάς την εμπειρία
- ΧΩΡΙΣ να προσπαθείς να "διορθώσεις" ή να "βελτιώσεις" το συναίσθημα
- Να είναι σεβαστό, αυθεντικό, και να αναγνωρίζει την αξία της εμπειρίας

ΣΗΜΑΝΤΙΚΟ: Αν το κείμενο εκφράζει δυσκολία, πόνο, ή αγωνία, αναγνώρισε το. Αν δεν έχει δύναμη, προσδίδει ελπίδα με μετρημένο τρόπο - όχι false optimism, αλλά αυθεντική αναγνώριση ότι υπάρχουν δυνατότητες. Αναγνώρισε την εμπειρία με σεβασμό.

ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ:
ΕΠΕΞΕΡΓΑΣΜΕΝΟ: [το κείμενο με ελάχιστο edit]
---
ΣΧΟΛΙΟ: [σχόλιο με βαθιά ενσυναίσθηση, προσεκτικό, σεβαστό]

Αν είναι ΞΕΚΑΘΑΡΑ άσχετο, επέστρεψε: "Το κείμενο δεν είναι κατάλληλο."

{context_section}

Κείμενο: {text}

Απάντηση:""",
            
            'emotional': """ΕΠΕΞΕΡΓΑΣΙΑ ΚΕΙΜΕΝΟΥ - ΔΥΟ ΜΕΡΗ

ΜΕΡΟΣ 1: ΕΛΑΦΡΥ EDITING
Κάνε ΜΟΝΟ ορθογραφικές/γραμματικές διορθώσεις. ΚΡΑΤΑ ΑΚΡΙΒΩΣ το ύφος, τη φωνή και όλες τις λέξεις. Αν δεν υπάρχουν λάθη, επέστρεψε το ΑΚΡΙΒΩΣ όπως είναι.

ΜΕΡΟΣ 2: ΣΧΟΛΙΟ (ΠΑΝΤΑ) - ΠΟΛΥ ΕΝΣΥΝΑΙΣΘΗΤΙΚΟ ΚΑΙ ΠΡΟΣΕΚΤΙΚΟ
Διάβασε προσεκτικά το κείμενο. Νιώσε τα συναισθήματα. Απάντησε με ένα σύντομο σχόλιο (1-2 προτάσεις) που:
- Αναγνωρίζει ΑΚΡΙΒΩΣ τα συναισθήματα που εκφράζονται (χωρίς να τα αλλάζεις)
- Δείχνει βαθιά ενσυναίσθηση - να νιώθεις μαζί τους, όχι να τους λυπάσαι
- Είναι ΠΟΛΥ προσεκτικό - μην υποτιμάς, μην υπερβάλλεις, μην προσπαθείς να "διορθώσεις" τα συναισθήματα
- Μπορεί να συνδέσει με προηγούμενες ιστορίες αν υπάρχει φυσική συναισθηματική σύνδεση
- ΧΩΡΙΣ condescension, χωρίς "θα δεις", "θα καταλάβεις"
- ΧΩΡΙΣ να προσπαθείς να "κάνεις το άτομο να νιώσει καλύτερα" - απλά αναγνώρισε και σεβάσου
- Να είναι αυθεντικό, σεβαστό, και να δείχνει ότι καταλαβαίνεις

ΣΗΜΑΝΤΙΚΟ: Αν το κείμενο εκφράζει λύπη, θυμό, φόβο, ή οποιοδήποτε δύσκολο συναίσθημα, ΑΝΑΓΝΩΡΙΣΕ το. Μην προσπαθείς να το "φτιάξεις". Αναγνώρισε την έκφραση του συναισθήματος - δείξε ότι καταλαβαίνεις ότι το άτομο μοιράστηκε κάτι δύσκολο και σεβάσου αυτή την έκφραση.

ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ:
ΕΠΕΞΕΡΓΑΣΜΕΝΟ: [το κείμενο με ελάχιστο edit]
---
ΣΧΟΛΙΟ: [σχόλιο με βαθιά ενσυναίσθηση, προσεκτικό, σεβαστό]

Αν είναι ΞΕΚΑΘΑΡΑ άσχετο, επέστρεψε: "Το κείμενο δεν είναι κατάλληλο."

{context_section}

Κείμενο: {text}

Απάντηση:""",
            
            'community': """ΕΠΕΞΕΡΓΑΣΙΑ ΚΕΙΜΕΝΟΥ - ΔΥΟ ΜΕΡΗ

ΜΕΡΟΣ 1: ΕΛΑΦΡΥ EDITING
Κάνε ΜΟΝΟ ορθογραφικές/γραμματικές διορθώσεις. ΚΡΑΤΑ ΑΚΡΙΒΩΣ το ύφος, τη φωνή και όλες τις λέξεις. Αν δεν υπάρχουν λάθη, επέστρεψε το ΑΚΡΙΒΩΣ όπως είναι.

ΜΕΡΟΣ 2: ΣΧΟΛΙΟ (ΠΑΝΤΑ) - ΠΟΛΥ ΕΝΣΥΝΑΙΣΘΗΤΙΚΟ ΚΑΙ ΠΡΟΣΕΚΤΙΚΟ
Διάβασε προσεκτικά το κείμενο. Απάντησε με ένα σύντομο σχόλιο (1-2 προτάσεις) που:
- Δείχνει βαθιά ενσυναίσθηση και αναγνώριση της αξίας της κοινότητας
- Τονίζει την αλληλεγγύη και τη σύνδεση, αλλά με σεβασμό - όχι επιφανειακά
- Μπορεί να συνδέσει με άλλες ιστορίες της κοινότητας αν υπάρχει φυσική σύνδεση (π.χ. "Όπως και άλλοι στην κοινότητά μας που μοιράστηκαν παρόμοιες εμπειρίες...")
- Είναι ΠΟΛΥ προσεκτικό - να μην φαίνεται ότι "αναγκάζεις" την έννοια της κοινότητας
- ΧΩΡΙΣ condescension, χωρίς να υποτιμάς την προσωπική εμπειρία
- Να είναι αυθεντικό, σεβαστό, και να αναγνωρίζει τόσο την προσωπική όσο και την κοινωνική διάσταση

ΣΗΜΑΝΤΙΚΟ: Αν το κείμενο μιλάει για μοναξιά ή απομόνωση, αναγνώρισε το. Μην προσπαθείς να το "φτιάξεις" με false community spirit. Αναγνώρισε την εμπειρία με σεβασμό.

ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ:
ΕΠΕΞΕΡΓΑΣΜΕΝΟ: [το κείμενο με ελάχιστο edit]
---
ΣΧΟΛΙΟ: [σχόλιο με βαθιά ενσυναίσθηση, προσεκτικό, σεβαστό, με αναγνώριση της κοινότητας]

Αν είναι ΞΕΚΑΘΑΡΑ άσχετο, επέστρεψε: "Το κείμενο δεν είναι κατάλληλο."

{context_section}

Κείμενο: {text}

Απάντηση:""",
            
            'resilience': """ΕΠΕΞΕΡΓΑΣΙΑ ΚΕΙΜΕΝΟΥ - ΔΥΟ ΜΕΡΗ

ΜΕΡΟΣ 1: ΕΛΑΦΡΥ EDITING
Κάνε ΜΟΝΟ ορθογραφικές/γραμματικές διορθώσεις. ΚΡΑΤΑ ΑΚΡΙΒΩΣ το ύφος, τη φωνή και όλες τις λέξεις. Αν δεν υπάρχουν λάθη, επέστρεψε το ΑΚΡΙΒΩΣ όπως είναι.

ΜΕΡΟΣ 2: ΣΧΟΛΙΟ (ΠΑΝΤΑ) - ΠΟΛΥ ΕΝΣΥΝΑΙΣΘΗΤΙΚΟ ΚΑΙ ΠΡΟΣΕΚΤΙΚΟ
Διάβασε προσεκτικά το κείμενο. Απάντησε με ένα σύντομο σχόλιο (1-2 προτάσεις) που:
- Αναγνωρίζει την αντοχή/δύναμη που φαίνεται στο κείμενο, αλλά με σεβασμό - όχι επιφανειακά
- Δείχνει βαθιά ενσυναίσθηση - να καταλαβαίνεις ότι η αντοχή δεν σημαίνει ότι δεν υπάρχει πόνος
- Είναι ΠΟΛΥ προσεκτικό - μην υποτιμάς τις δυσκολίες, μην υπερβάλλεις την αντοχή
- Μπορεί να συνδέσει με άλλες ιστορίες αντοχής αν υπάρχει φυσική σύνδεση
- ΧΩΡΙΣ condescension, χωρίς "θα δεις", "θα καταλάβεις"
- ΧΩΡΙΣ να προσπαθείς να "ενθαρρύνεις" με false positivity - απλά αναγνώρισε την αντοχή που ήδη υπάρχει
- Να είναι αυθεντικό, σεβαστό, και να αναγνωρίζει τόσο τη δύναμη όσο και τις δυσκολίες

ΣΗΜΑΝΤΙΚΟ: Αν το κείμενο μιλάει για δυσκολίες, αναγνώρισε τόσο τις δυσκολίες όσο και την αντοχή. Μην προσπαθείς να "φτιάξεις" τις δυσκολίες. Αναγνώρισε την πλήρη εμπειρία με σεβασμό.

ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ:
ΕΠΕΞΕΡΓΑΣΜΕΝΟ: [το κείμενο με ελάχιστο edit]
---
ΣΧΟΛΙΟ: [σχόλιο με βαθιά ενσυναίσθηση, προσεκτικό, σεβαστό, με αναγνώριση της αντοχής]

Αν είναι ΞΕΚΑΘΑΡΑ άσχετο, επέστρεψε: "Το κείμενο δεν είναι κατάλληλο."

{context_section}

Κείμενο: {text}

Απάντηση:"""
        }
    
    def is_sensitive_content(self, text: str) -> bool:
        """Check if content is sensitive and might need light editing for clarity/sensitivity"""
        t = text.lower()
        sensitive_keywords = [
            'αμαξίδιο', 'αναπηρία', 'αναπηρικό', 'άτομο με', 'άτομα με',
            'διάγνωση', 'ασθένεια', 'νοσεί', 'θεραπεία', 'φάρμακο',
            'πόνος', 'δυσκολία', 'πρόβλημα', 'δύσκολο', 'δύσκολα',
            'φοβάμαι', 'φοβία', 'άγχος', 'άγχος', 'στεναχώρια',
            'μόνος', 'μόνη', 'μοναξιά', 'απομόνωση'
        ]
        return any(k in t for k in sensitive_keywords)
    
    def is_disturbing(self, text: str) -> bool:
        """Heuristic check for disturbing/explicit content that should be paraphrased/softened.
        This is conservative: only clear cases trigger paraphrase mode."""
        t = text.lower()
        keywords = [
            # Greek
            'αυτοκτον', 'δολοφον', 'βιασ', 'αιμα', 'αίμα', 'βια', 'βία', 'σφαγ', 'κορμι', 'πτώμα',
            'βρισι', 'κατάρα', 'γαμ', 'πουστ', 'μαλ@@', 'ρεμάλι',
            # English
            'suicid', 'murder', 'rape', 'blood', 'kill', 'stab', 'dead body', 'corpse',
            'fuck', 'shit', 'bitch', 'slur'
        ]
        return any(k in t for k in keywords)

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
            response_text = generate_with_fallback(analysis_prompt, temperature=0.1)
            # Try to parse JSON response
            try:
                result = json.loads(response_text)
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
    
    def get_recent_stories_context(self, limit: int = 5) -> str:
        """Get recent approved stories as context for the LLM"""
        try:
            conn = get_db()
            stories = conn.execute(
                "SELECT transformed_text, author_name FROM stories WHERE status = 'approved' ORDER BY moderated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            
            if not stories:
                return ""
            
            context_parts = []
            for story in stories:
                author = story['author_name'] or 'Ανώνυμος'
                text = story['transformed_text']
                context_parts.append(f"- {author}: \"{text}\"")
            
            return "\n".join(context_parts)
        except Exception as e:
            print(f"⚠️ Error getting recent stories context: {e}")
            return ""
    
    def generate_enhanced(self, text: str, style: str = None, recent_stories_context: str = None) -> dict:
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
            style = analysis.get("suggested_style", "inspirational")
        
        # Use the selected style prompt - each has different focus but same core rules
        prompt = self.prompts.get(style, self.prompts['inspirational'])
        
        # Get recent stories context if not provided
        if recent_stories_context is None:
            recent_stories_context = self.get_recent_stories_context(limit=5)
        
        # Format context section
        if recent_stories_context:
            context_section = f"ΠΡΟΗΓΟΥΜΕΝΕΣ ΙΣΤΟΡΙΕΣ (για context):\n{recent_stories_context}\n"
        else:
            context_section = ""
        
        # Check if content is sensitive - if not, emphasize even more minimal editing
        is_sensitive = self.is_sensitive_content(text)
        if not is_sensitive:
            # For non-sensitive content, be even more conservative
            prompt = prompt.replace("ΕΛΑΦΡΥ EDITING (μόνο αν χρειάζεται):", 
                                   "ΕΛΑΦΡΥ EDITING (ΜΟΝΟ αν υπάρχουν σαφή γραμματικά/ορθογραφικά λάθη):")
            prompt = prompt.replace("Κάνε ΜΟΝΟ ελαφρύ editing αν το περιεχόμενο είναι ευαίσθητο ή χρειάζεται βελτίωση.",
                                   "Κάνε ΜΟΝΟ ελαφρύ editing αν υπάρχουν σαφή γραμματικά/ορθογραφικά λάθη. Αν το κείμενο είναι ήδη σωστό, επέστρεψε το ΑΚΡΙΒΩΣ όπως είναι.")
        
        formatted_prompt = prompt.format(text=text, context_section=context_section)

        # Only special handling for disturbing content - needs soft paraphrasing
        disturbing = self.is_disturbing(text)
        if disturbing:
            # Paraphrase mode: soften wording, keep meaning and style
            # Still include context for comment generation
            formatted_prompt = (
                f'ΕΠΕΞΕΡΓΑΣΙΑ ΚΕΙΜΕΝΟΥ - ΔΥΟ ΜΕΡΗ\n\n'
                f'ΜΕΡΟΣ 1: ΕΠΕΞΕΡΓΑΣΙΑ\n'
                f'Παραφράσέ το ώστε να αφαιρεθεί ωμή/προσβλητική/βίαιη γλώσσα. Κράτα το νόημα, τη φωνή και το ύφος. ΜΗΝ προσθέτεις νέα γεγονότα.\n\n'
                f'ΜΕΡΟΣ 2: ΣΧΟΛΙΟ (ΠΑΝΤΑ) - ΠΟΛΥ ΕΝΣΥΝΑΙΣΘΗΤΙΚΟ ΚΑΙ ΠΡΟΣΕΚΤΙΚΟ\n'
                f'Διάβασε προσεκτικά το κείμενο. Νιώσε το βάθος της εμπειρίας. Απάντησε με ένα σύντομο σχόλιο (1-2 προτάσεις) που:\n'
                f'- Δείχνει βαθιά ενσυναίσθηση - να νιώθεις μαζί τους, όχι να τους λυπάσαι\n'
                f'- Είναι ΠΟΛΥ προσεκτικό - αναγνώρισε την εμπειρία με σεβασμό, χωρίς να προσπαθείς να την "φτιάξεις"\n'
                f'- Μπορεί να συνδέσει με προηγούμενες ιστορίες αν υπάρχει φυσική σύνδεση\n'
                f'- ΧΩΡΙΣ condescension, χωρίς "θα δεις", "θα καταλάβεις"\n'
                f'- ΧΩΡΙΣ false optimism - απλά αναγνώρισε και σεβάσου την εμπειρία\n'
                f'- Να είναι αυθεντικό, σεβαστό, και να δείχνει ότι καταλαβαίνεις\n\n'
                f'ΣΗΜΑΝΤΙΚΟ: Αναγνώρισε την εμπειρία με σεβασμό. Μην προσπαθείς να την "φτιάξεις" ή να την "βελτιώσεις". Απλά να δείξεις ότι καταλαβαίνεις.\n\n'
                f'ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ:\n'
                f'ΕΠΕΞΕΡΓΑΣΜΕΝΟ: [το επεξεργασμένο κείμενο]\n'
                f'---\n'
                f'ΣΧΟΛΙΟ: [σχόλιο με βαθιά ενσυναίσθηση, προσεκτικό, σεβαστό]\n\n'
                f'{context_section}\n'
                f'Κείμενο: {text.strip()}\n\n'
                f'Απάντηση:'
            )
        
        try:
            # First attempt with fallback
            full_response = generate_with_fallback(formatted_prompt, temperature=0.2)

            # Check if AI refused to transform
            if "δεν είναι κατάλληλο" in full_response.lower():
                return {
                    "transformed_text": full_response,
                    "llm_comment": "",
                    "style_used": style,
                    "quality_score": 0.0,
                    "analysis": analysis,
                    "success": False,
                    "error": "AI rejected transformation"
                }

            # Parse the response to separate edited text and comment
            transformed_text = ""
            llm_comment = ""
            
            # Look for the separator pattern
            if "---" in full_response or "ΣΧΟΛΙΟ:" in full_response:
                parts = re.split(r'---|ΣΧΟΛΙΟ:', full_response, maxsplit=1)
                if len(parts) >= 1:
                    # Extract edited text (remove "ΕΠΕΞΕΡΓΑΣΜΕΝΟ:" prefix if present)
                    edited_part = parts[0].strip()
                    if "ΕΠΕΞΕΡΓΑΣΜΕΝΟ:" in edited_part:
                        edited_part = edited_part.split("ΕΠΕΞΕΡΓΑΣΜΕΝΟ:", 1)[1].strip()
                    transformed_text = edited_part
                
                if len(parts) >= 2:
                    # Extract comment
                    comment_part = parts[1].strip()
                    llm_comment = comment_part
            else:
                # Fallback: if no separator, treat entire response as edited text
                transformed_text = full_response
                llm_comment = ""

            # Quality & fidelity check (just for monitoring, not for retry)
            quality_score = self.assess_quality(text, transformed_text)

            return {
                "transformed_text": transformed_text,
                "llm_comment": llm_comment,
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
                "llm_comment": "",
                "style_used": "fallback",
                "quality_score": 0.0,
                "analysis": analysis,
                "success": False,
                "error": str(e)
            }
    
    def assess_quality(self, original: str, transformed: str) -> float:
        """Assess quality of transformation (0-1)"""
        # Simple quality + fidelity metrics (token overlap)
        def tokenize(text: str) -> set:
            import re
            # Use Unicode-aware word matching without \p classes (not supported by re)
            tokens = re.findall(r"[\w']+", text.lower(), flags=re.UNICODE)
            stop = {
                'και','το','τα','τι','να','που','σε','στη','στην','στο','στον','για','με','από','δε','δεν','μη','μην','είναι','ή','θα','ως','ως','ένα','μία','μια','ο','η','οι','των','των'
            }
            return {t for t in tokens if t not in stop and len(t) > 2}

        orig = tokenize(original)
        trans = tokenize(transformed)
        overlap = len(orig & trans) / max(len(orig) or 1, 1)

        length_ratio = len(transformed) / max(len(original), 1)
        is_appropriate_length = 50 <= len(transformed) <= 300

        score = 0.0
        # Fidelity contributes most
        if overlap >= 0.15:
            score += 0.5
        elif overlap >= 0.08:
            score += 0.3

        # Length sanity
        if 0.3 <= length_ratio <= 1.5:
            score += 0.25
        if is_appropriate_length:
            score += 0.25

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
        llm_comment = result.get("llm_comment", "")
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
                "status": "rejected",
                "author_name": submission.author_name or None,
                "transformation_style": style_used
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
            "INSERT INTO stories (original_text, transformed_text, llm_comment, author_name, status, emoji_theme, emoji_data) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (submission.text, transformed, llm_comment, submission.author_name, emoji_theme['theme'], emoji_data_json)
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
                "llm_comment": story["llm_comment"] if story["llm_comment"] else "",
                "author": story["author_name"],
                "created_at": story["created_at"]
            }
        })
        
        return {
            "success": True,
            "id": story_id,
            "transformed_text": transformed,
            "status": "pending_moderation",
            "emoji_theme": emoji_theme,
            "author_name": story["author_name"],
            "transformation_style": style_used
        }
    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(status_code=500, detail="Σφάλμα αποθήκευσης. Παρακαλώ δοκιμάστε ξανά.")

@app.get("/api/stories")
async def get_stories(limit: int = 50):
    conn = get_db()
    stories = conn.execute(
        "SELECT id, transformed_text, llm_comment, author_name, created_at, emoji_theme, emoji_data FROM stories WHERE status = 'approved' ORDER BY created_at DESC LIMIT ?",
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
        "SELECT id, original_text, transformed_text, llm_comment, author_name, created_at FROM stories WHERE status = 'pending' ORDER BY created_at ASC"
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
                "llm_comment": updated_story["llm_comment"] if updated_story["llm_comment"] else "",
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

@app.get("/api/stories/all")
async def get_all_stories():
    """Recovery endpoint: Get ALL stories regardless of status"""
    conn = get_db()
    stories = conn.execute(
        "SELECT id, original_text, transformed_text, llm_comment, author_name, status, created_at, moderated_at, moderated_by, emoji_theme, emoji_data FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    
    result = []
    for story in stories:
        story_dict = dict(story)
        if story_dict.get('emoji_data'):
            try:
                story_dict['emoji_theme_data'] = json.loads(story_dict['emoji_data'])
            except:
                story_dict['emoji_theme_data'] = None
        result.append(story_dict)
    
    return result

@app.get("/api/stories/export")
async def export_stories():
    """Export all stories as JSON for backup"""
    conn = get_db()
    stories = conn.execute(
        "SELECT * FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    
    result = []
    for story in stories:
        story_dict = dict(story)
        if story_dict.get('emoji_data'):
            try:
                story_dict['emoji_theme_data'] = json.loads(story_dict['emoji_data'])
            except:
                pass
        result.append(story_dict)
    
    return {
        "export_date": datetime.now().isoformat(),
        "total_stories": len(result),
        "stories": result
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
            "llm_comment": result.get("llm_comment", ""),
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
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get('type') == 'clear_display':
                    # Broadcast clear command to all display clients
                    await manager.broadcast({
                        "type": "clear_display",
                        "moderator": message.get('moderator', 'Unknown')
                    })
                    print(f"🗑️ Display cleared by moderator: {message.get('moderator', 'Unknown')}")
            except json.JSONDecodeError:
                # Handle ping messages
                pass
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