# BookMarketabilityChecker.py - COMPLETE FIXED VERSION
import streamlit as st
import openai
import PyPDF2
import docx
import json
import base64
from PIL import Image
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Initialize OpenAI with secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Email config from secrets
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = st.secrets["SMTP_PORT"]
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
USE_TLS = st.secrets.get("use_tls", True)

def count_words(text):
    """Count words in text"""
    return len(text.split())

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, word_count):
    """Send full analysis results via email"""
    
    marketability = analysis_results.get('marketability', {})
    score = marketability.get('overall_score', 0)
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
    
    subject = f"Your Book Analysis: {book_title} by {author_name}"
    
    # Word count warning
    word_count_warning = ""
    if word_count < 70000:
        word_count_warning = f"""
        <div style="padding: 15px; background: #ff8800; border-radius: 10px; margin-top: 20px; color: white;">
            <strong>⚠️ Word Count Warning:</strong> Your manuscript is {word_count:,} words. For most genres, target 70,000-100,000 words for publication.
        </div>
        """
    elif word_count > 100000:
        word_count_warning = f"""
        <div style="padding: 15px; background: #ff8800; border-radius: 10px; margin-top: 20px; color: white;">
            <strong>⚠️ Word Count Warning:</strong> Your manuscript is {word_count:,} words. This is longer than typical for most genres (70,000-100,000).
        </div>
        """
    
    # Different message based on score
    if score >= 70:
        next_steps = "✅ Your book is ready for marketing! Click below to get started with BardSpark."
        cta_text = "START MARKETING YOUR BOOK"
        cta_color = "#00cc66"
    else:
        next_steps = "📝 Your book needs more work before marketing. We've included detailed feedback below."
        cta_text = "GET EDITING RESOURCES"
        cta_color = "#ff8800"
    
    # Build email body
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0; opacity: 0.9;">by {author_name}</h3>
            <div style="font-size: 48px; font-weight: bold; margin: 20px 0;">{score} ({grade})</div>
            <p>Marketability Score</p>
            <p style="font-size: 14px; margin-top: 10px;">Word Count: {word_count:,}</p>
        </div>
        
        {word_count_warning}
        
        <div style="padding: 20px; background: {cta_color}; border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <p style="font-size: 16px;">{next_steps}</p>
        </div>
    """
    
    # Book Overview
    body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📖 Book Overview</h2>
            <p><strong>Genre:</strong> {book_info.get('genre', 'Unknown')}</p>
            <p><strong>Tone:</strong> {book_info.get('tone', 'Unknown')}</p>
            <p><strong>Writing Style:</strong> {book_info.get('writing_style', 'Unknown')}</p>
            <p><strong>Pacing:</strong> {book_info.get('pacing_summary', 'Unknown')}</p>
        </div>
    """
    
    # Overall Assessment
    body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📊 Overall Assessment</h2>
            <p>{marketability.get('overall_assessment', '')}</p>
        </div>
    """
    
    # Detailed Scores with color coding
    body += """
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📈 Detailed Scores</h2>
    """
    
    scores = marketability.get('scores', {})
    for score_name, score_data in scores.items():
        display_name = score_name.replace('_', ' ').title()
        score_value = score_data.get('score', 0)
        explanation = score_data.get('explanation', '')
        
        # Color code the bar
        if score_value >= 80:
            bar_color = "#00cc66"
        elif score_value >= 70:
            bar_color = "#ffaa00"
        elif score_value >= 60:
            bar_color = "#ff8800"
        else:
            bar_color = "#ff4444"
        
        body += f"""
            <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <strong>{display_name}</strong> <span style="font-weight: bold; color: {bar_color};">{score_value}</span>
                </div>
                <div style="height: 10px; background: #eee; border-radius: 5px; margin-bottom: 5px;">
                    <div style="width: {score_value}%; height: 10px; background: {bar_color}; border-radius: 5px;"></div>
                </div>
                <p style="color: #666; font-size: 14px; margin: 0;">{explanation}</p>
            </div>
        """
    body += "</div>"
    
    # Writing Quality
    if 'writing_quality_detailed' in analysis_results:
        writing = analysis_results['writing_quality_detailed']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>✍️ Writing Quality Analysis</h2>
            <p><strong>Prose Quality:</strong> {writing.get('prose_quality', '')}</p>
            <p><strong>Dialogue:</strong> {writing.get('dialogue', '')}</p>
            <p><strong>Voice:</strong> {writing.get('voice', '')}</p>
        </div>
        """
    
    # Characters
    if 'characters' in analysis_results:
        chars = analysis_results['characters']
        body += """
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>👥 Main Characters</h2>
        """
        for char in chars.get('main', [])[:3]:
            body += f"""
            <div style="margin-bottom: 15px; padding: 10px; background: white; border-radius: 5px;">
                <strong>{char.get('name', 'Unknown')}</strong> - {char.get('role', '')}<br>
                <p style="margin: 5px 0 0 0; color: #666;">{char.get('description', '')}</p>
            </div>
            """
        body += "</div>"
    
    # Narrative Arc
    if 'narrative_arc' in analysis_results:
        arc = analysis_results['narrative_arc']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📖 Narrative Arc</h2>
            <p><strong>Exposition:</strong> {arc.get('exposition', '')}</p>
            <p><strong>Rising Action:</strong> {arc.get('rising_action', '')}</p>
            <p><strong>Climax:</strong> {arc.get('climax', '')}</p>
            <p><strong>Resolution:</strong> {arc.get('resolution', '')}</p>
        </div>
        """
    
    # Themes
    if 'themes' in analysis_results:
        themes = analysis_results['themes']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>🎯 Themes</h2>
            <p><strong>Primary:</strong> {', '.join(themes.get('primary', []))}</p>
        </div>
        """
    
    # Cover analysis if available
    if cover_analysis:
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎨 Cover Analysis</h2>
            <p><strong>Mood:</strong> {cover_analysis.get('mood', 'N/A')}</p>
            <p><strong>Genre Signals:</strong> {cover_analysis.get('genre_signals', 'N/A')}</p>
            <p><strong>Strengths:</strong> {', '.join(cover_analysis.get('strengths', ['N/A']))}</p>
            <p><strong>Weaknesses:</strong> {', '.join(cover_analysis.get('weaknesses', ['N/A']))}</p>
        </div>
        """
    
    # Strengths & Improvements
    body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>💪 Key Strengths</h2>
            <ul>
    """
    for strength in analysis_results.get('strengths', [])[:5]:
        body += f"<li>{strength}</li>"
    
    body += """
            </ul>
        </div>
        
        <div style="padding: 20px; margin-top: 20px;">
            <h2>🔧 Areas for Improvement</h2>
            <ul>
    """
    for area in analysis_results.get('areas_for_improvement', [])[:5]:
        body += f"<li>{area}</li>"
    
    body += """
            </ul>
        </div>
    """
    
    # Call to action - different based on score
    if score >= 70:
        body += f"""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Your book is ready for marketing!</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <a href="https://yourapp.com/signup" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">START MARKETING NOW</a>
        </div>
        """
    else:
        body += f"""
        <div style="padding: 30px; background: #ff8800; border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>📝 Your book needs work before marketing</h2>
            <p style="font-size: 18px;">We recommend focusing on:</p>
            <ul style="text-align: left; display: inline-block;">
                <li>Addressing the areas for improvement above</li>
                <li>Getting professional editing</li>
                <li>Beta reader feedback</li>
                <li>Structural revisions</li>
            </ul>
            <p style="margin-top: 20px;">Come back when your book scores 70+!</p>
        </div>
        """
    
    body += f"""
        <p style="color: #999; font-size: 12px; text-align: center; margin-top: 30px;">
            Analysis performed on {datetime.now().strftime('%B %d, %Y')}
        </p>
    </body>
    </html>
    """
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email sending failed: {e}")
        return False

def show_marketability_checker():
    """Marketability checker that filters bad books"""
    
    st.set_page_config(
        page_title="Free Book Analysis",
        page_icon="📊",
        layout="centered"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            text-align: center;
            padding: 2rem 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        .feature-box {
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #667eea;
        }
        .warning-box {
            padding: 1.5rem;
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 10px;
            margin: 1.5rem 0;
            border-left: 5px solid #ff8800;
        }
        .score-box {
            text-align: center;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            margin: 2rem 0;
            color: white;
        }
        .score-number {
            font-size: 72px;
            font-weight: bold;
            margin: 0;
        }
        .score-label {
            font-size: 24px;
            margin: 0;
        }
        .filter-message {
            text-align: center;
            padding: 1.5rem;
            background: #f0f2f6;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 5px solid #667eea;
            font-size: 16px;
        }
        .word-count-box {
            padding: 1rem;
            background: #e1f5fe;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #03a9f4;
        }
        .success-message {
            text-align: center;
            padding: 2rem;
            background: #d4edda;
            border-radius: 10px;
            margin: 2rem 0;
            border-left: 5px solid #28a745;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Free Book Analysis</h1>
        <p>Get your COMPLETE book analysis emailed to you in 60 seconds</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filter message
    st.markdown("""
    <div class="filter-message">
        <strong>📊 The Hard Truth:</strong> Most books sell less than 100 copies, no matter how much effort you put into marketing.<br>
        <strong>A bad book will never sell.</strong><br><br>
        This is why we ONLY accept books with a marketability score of <strong>70+ into BardSpark</strong>.<br>
        If your book scores lower, we'll tell you exactly what needs work.
    </div>
    """, unsafe_allow_html=True)
    
    # Word count info
    st.markdown("""
    <div class="word-count-box">
        <strong>📏 Word Count Guide:</strong> For most genres, target 70,000-100,000 words for publication.<br>
        <em>(If you're testing an unfinished manuscript, that's fine - we'll still analyze it!)</em>
    </div>
    """, unsafe_allow_html=True)
    
    # What they get
    with st.expander("📋 What's included in your free analysis", expanded=True):
        st.markdown("""
        - 📖 **Full book analysis** (genre, tone, writing style, pacing)
        - 📊 **Marketability score** with detailed breakdown
        - ✍️ **Writing quality assessment** (prose, dialogue, voice)
        - 👥 **Character analysis** (main characters and their roles)
        - 📈 **Narrative arc** (exposition, rising action, climax, resolution)
        - 🎯 **Theme identification** and motif analysis
        - 💪 **Key strengths** of your manuscript
        - 🔧 **Areas for improvement** with specific suggestions
        - 🎨 **Cover analysis** (if you upload it)
        - 📏 **Word count analysis** with genre-specific guidance
        """)
    
    st.markdown("---")
    
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cover_analysis' not in st.session_state:
        st.session_state.cover_analysis = None
    if 'word_count' not in st.session_state:
        st.session_state.word_count = 0
    if 'email_sent' not in st.session_state:
        st.session_state.email_sent = False
    
    if not st.session_state.analysis_complete:
        show_upload_section()
    else:
        show_success_section()

def show_upload_section():
    """Show file upload interface"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📄 Manuscript (required)**")
        manuscript = st.file_uploader(
            "Upload PDF, DOCX, or TXT",
            type=['pdf', 'docx', 'txt'],
            key="manuscript",
            label_visibility="collapsed"
        )
        if manuscript:
            file_size = len(manuscript.getvalue()) / 1024
            st.success(f"✅ {manuscript.name} ({file_size:.0f} KB)")
    
    with col2:
        st.markdown("**🎨 Cover Image (optional but recommended)**")
        cover = st.file_uploader(
            "Upload JPG or PNG",
            type=['jpg', 'jpeg', 'png'],
            key="cover",
            label_visibility="collapsed"
        )
        if cover:
            st.success(f"✅ {cover.name}")
            image = Image.open(cover)
            st.image(image, width=100)
    
    st.markdown("---")
    st.markdown("### 📧 Where should we send your complete analysis?")
    
    email = st.text_input("Email address", placeholder="you@example.com")
    
    st.markdown("""
    <p style="font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 20px;">
        We'll never spam you. Just this one analysis.
    </p>
    """, unsafe_allow_html=True)
    
    if manuscript and email:
        if st.button("🔍 GET MY FREE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 60 seconds)"):
                
                # Extract full manuscript
                text = extract_text_full(manuscript)
                
                # Count words
                word_count = count_words(text)
                st.session_state.word_count = word_count
                
                # Process cover if provided
                cover_analysis = None
                if cover:
                    cover_bytes = cover.getvalue()
                    cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
                    cover_analysis = analyze_cover(cover_base64)
                    st.session_state.cover_analysis = cover_analysis
                
                # Analyze manuscript
                analysis = analyze_book_complete(text, cover_analysis, word_count)
                
                if analysis:
                    st.session_state.analysis_result = analysis
                    
                    # Get book title and author
                    book_info = analysis.get('book_info', {})
                    book_title = book_info.get('title', 'Your Book')
                    author_name = book_info.get('author', 'Unknown Author')
                    
                    # SEND EMAIL
                    email_sent = send_email(email, analysis, cover_analysis, book_title, author_name, word_count)
                    
                    if email_sent:
                        st.session_state.analysis_complete = True
                        st.session_state.book_title = book_title
                        st.session_state.author_name = author_name
                        st.session_state.email_sent = True
                        st.rerun()
                    else:
                        st.error("Failed to send email. Please check your email settings and try again.")
                else:
                    st.error("Analysis failed. Please try again.")
    else:
        if not manuscript:
            st.info("👆 Please upload your manuscript")
        elif not email:
            st.info("👆 Please enter your email address")

def show_success_section():
    """Show success message only - NO RESULTS DISPLAYED"""
    
    st.markdown(f"""
    <div class="success-message">
        <h2>✅ Analysis Complete!</h2>
        <p style="font-size: 18px;">We've sent your complete analysis to your email.</p>
        <p>Book: <strong>{st.session_state.book_title}</strong> by <strong>{st.session_state.author_name}</strong></p>
        <p>Word Count: {st.session_state.word_count:,}</p>
        <p style="margin-top: 20px;">📧 Check your inbox (and spam folder)</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Analyze Another Book", use_container_width=True):
        st.session_state.analysis_complete = False
        st.session_state.analysis_result = None
        st.session_state.cover_analysis = None
        st.session_state.email_sent = False
        st.rerun()

def analyze_cover(cover_base64):
    """Full cover analysis"""
    
    prompt = """Analyze this book cover in detail. Return JSON with:
    {
        "colors": ["list of dominant colors"],
        "has_figure": true/false,
        "figure_description": "description if any figures present",
        "typography": "description of font style",
        "composition": "how elements are arranged",
        "mood": "emotional feeling",
        "genre_signals": "what genre this suggests",
        "strengths": ["3 specific strengths"],
        "weaknesses": ["3 specific weaknesses"],
        "suggestions": ["3 improvements"]
    }"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{cover_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except:
        return None

def analyze_book_complete(text, cover_analysis, word_count):
    """Complete book analysis with calibrated scoring"""
    
    if len(text) > 50000:
        text = text[:50000] + "... [truncated]"
    
    total_len = len(text)
    beginning = text[:min(5000, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:5000]
    ending = text[-5000:]
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis, indent=2)}"
    
    # Extract title and author from first few lines
    first_lines = text[:1000].split('\n')
    detected_title = "Unknown Title"
    detected_author = "Unknown Author"
    
    for i, line in enumerate(first_lines):
        line = line.strip()
        if line and len(line) > 5 and not line.startswith(' ') and not line.startswith('\t'):
            if i == 0:
                detected_title = line
            elif i == 1 and ('by' in line.lower() or 'BY' in line):
                detected_author = line.replace('by', '').replace('BY', '').strip()
            break
    
    for i, line in enumerate(first_lines):
        if 'by' in line.lower() and len(line) < 50:
            detected_author = line.replace('by', '').replace('BY', '').strip()
            if i > 0 and first_lines[i-1].strip():
                detected_title = first_lines[i-1].strip()
    
    word_count_note = ""
    if word_count < 70000:
        word_count_note = f"Note: This manuscript is {word_count} words, which is below the typical 70,000-100,000 range for publication."
    elif word_count > 100000:
        word_count_note = f"Note: This manuscript is {word_count} words, which is above the typical 70,000-100,000 range for publication."
    
    prompt = f"""
    You are a professional literary analyst. Analyze THIS SPECIFIC BOOK based SOLELY on the manuscript excerpts provided below.
    
    CALIBRATION REFERENCE:
    - A professionally written, well-structured novel with compelling characters should score 85+
    - A decent but flawed manuscript with some issues should score 70-84
    - An amateur memoir with no plot, flat characters, and rambling structure should score 40-50
    - A poorly written manuscript with basic errors should score below 40
    
    BOOK TITLE: {detected_title}
    AUTHOR: {detected_author}
    WORD COUNT: {word_count} words
    {word_count_note}
    
    {cover_text}
    
    ACTUAL MANUSCRIPT EXCERPTS:
    
    BEGINNING:
    {beginning}
    
    MIDDLE:
    {middle}
    
    ENDING:
    {ending}
    
    Return JSON with these sections:
    
    {{
        "marketability": {{
            "overall_score": (0-100 based on the calibration reference above),
            "overall_grade": ("A", "B", "C", "D", "F" with +/-),
            "overall_assessment": "One honest sentence about this book's potential",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": "Based on prose quality in excerpts"}},
                "commercial_potential": {{"score": 0-100, "explanation": "Based on hook and marketability"}},
                "genre_fit": {{"score": 0-100, "explanation": "How well it fits genre conventions"}},
                "hook_strength": {{"score": 0-100, "explanation": "Based on the opening excerpt"}},
                "character_appeal": {{"score": 0-100, "explanation": "Based on characters shown"}},
                "pacing": {{"score": 0-100, "explanation": "Based on flow between excerpts"}},
                "originality": {{"score": 0-100, "explanation": "Unique elements observed"}}
            }}
        }},
        
        "writing_quality_detailed": {{
            "prose_quality": "Assessment of sentence-level writing",
            "dialogue": "Quality of dialogue (if any)",
            "description": "Quality of descriptive passages",
            "voice": "Strength of narrative voice",
            "technical_execution": "Grammar and punctuation notes"
        }},
        
        "book_info": {{
            "title": "{detected_title}",
            "author": "{detected_author}",
            "genre": "primary genre based on content",
            "subgenres": ["subgenre1", "subgenre2"],
            "tone": "overall emotional tone",
            "writing_style": "descriptive/lyrical/direct/etc",
            "pacing_summary": "fast/medium/slow"
        }},
        
        "characters": {{
            "main": [
                {{
                    "name": "character name from excerpts",
                    "role": "protagonist/antagonist/etc",
                    "description": "description based on excerpts",
                    "arc": "how they change (if any)",
                    "motivation": "what drives them (if shown)"
                }}
            ],
            "supporting": ["list other characters mentioned"],
            "total_characters_identified": "number of distinct characters"
        }},
        
        "narrative_arc": {{
            "exposition": "setup shown in beginning",
            "rising_action": "events in middle",
            "climax": "turning point (if any)",
            "falling_action": "aftermath (if any)",
            "resolution": "conclusion (if any)"
        }},
        
        "plot": {{
            "opening_hook": "what grabs attention",
            "inciting_incident": "what starts the story (if shown)",
            "major_plot_points": ["points from excerpts"],
            "plot_twists": ["any surprises"]
        }},
        
        "themes": {{
            "primary": ["main themes visible"],
            "secondary": ["other themes hinted at"]
        }},
        
        "strengths": ["5 specific strengths with examples from text"],
        
        "areas_for_improvement": ["5 specific weaknesses with concrete suggestions"],
        
        "target_audience": {{
            "primary": "who might enjoy this",
            "appeal": "why they'd enjoy it"
        }},
        
        "marketing": {{
            "unique_selling_points": ["what makes it special"],
            "blurb_suggestion": "A potential blurb"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional literary analyst. Score according to the calibration reference."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if 'book_info' not in result:
            result['book_info'] = {}
        result['book_info']['title'] = detected_title
        result['book_info']['author'] = detected_author
        
        return result
        
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        return None

def extract_text_full(file):
    """Extract entire manuscript"""
    try:
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text[:50000]
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text[:50000]
            
        else:
            text = file.getvalue().decode("utf-8")
            return text[:50000]
            
    except Exception as e:
        return f"Error extracting text: {str(e)}"

if __name__ == "__main__":
    show_marketability_checker()
