# BookMarketabilityChecker.py - FINAL WORKING VERSION
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
        cta_color = "#00cc66"
    else:
        next_steps = "📝 Your book needs more work before marketing. We've included detailed feedback below."
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
    
    # Call to action
    if score >= 70:
        body += f"""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Your book is ready for marketing!</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access all our marketing tools.</p>
            <a href="https://yourapp.com/signup" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">START MARKETING NOW</a>
        </div>
        """
    else:
        body += f"""
        <div style="padding: 30px; background: #ff8800; border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>📝 Your book needs work before marketing</h2>
            <p>Focus on the areas for improvement above.</p>
            <p>Come back when your book scores 70+!</p>
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
    """Main app"""
    
    st.set_page_config(
        page_title="Free Book Analysis",
        page_icon="📊",
        layout="centered"
    )
    
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
        .filter-message {
            text-align: center;
            padding: 1.5rem;
            background: #f0f2f6;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 5px solid #667eea;
        }
        .success-message {
            text-align: center;
            padding: 2rem;
            background: #d4edda;
            border-radius: 10px;
            margin: 2rem 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📊 Free Book Analysis</h1>
        <p>Get your complete analysis emailed in 60 seconds</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="filter-message">
        <strong>📊 The Hard Truth:</strong> Most books sell less than 100 copies.<br>
        <strong>A bad book will never sell.</strong><br><br>
        We only accept books scoring 70+ into BardSpark.
    </div>
    """, unsafe_allow_html=True)
    
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    
    if not st.session_state.analysis_complete:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📄 Manuscript**")
            manuscript = st.file_uploader(
                "Upload PDF, DOCX, or TXT",
                type=['pdf', 'docx', 'txt'],
                key="manuscript",
                label_visibility="collapsed"
            )
        
        with col2:
            st.markdown("**🎨 Cover (optional)**")
            cover = st.file_uploader(
                "Upload JPG or PNG",
                type=['jpg', 'jpeg', 'png'],
                key="cover",
                label_visibility="collapsed"
            )
            if cover:
                st.image(Image.open(cover), width=100)
        
        st.markdown("---")
        email = st.text_input("📧 Your email address", placeholder="you@example.com")
        st.markdown("<p style='font-size:12px; color:#666;'>We'll never spam you.</p>", unsafe_allow_html=True)
        
        if manuscript and email:
            if st.button("🔍 GET MY FREE ANALYSIS", type="primary", use_container_width=True):
                with st.spinner("Analyzing your book... (60 seconds)"):
                    
                    text = extract_text_full(manuscript)
                    word_count = count_words(text)
                    
                    cover_analysis = None
                    if cover:
                        cover_bytes = cover.getvalue()
                        cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
                        cover_analysis = analyze_cover(cover_base64)
                    
                    analysis = analyze_book_complete(text, cover_analysis, word_count)
                    
                    if analysis:
                        book_info = analysis.get('book_info', {})
                        book_title = book_info.get('title', 'Your Book')
                        author_name = book_info.get('author', 'Unknown Author')
                        
                        if send_email(email, analysis, cover_analysis, book_title, author_name, word_count):
                            st.session_state.analysis_complete = True
                            st.session_state.book_title = book_title
                            st.session_state.author_name = author_name
                            st.rerun()
        else:
            if not manuscript:
                st.info("👆 Upload your manuscript")
            elif not email:
                st.info("👆 Enter your email")
    else:
        st.markdown(f"""
        <div class="success-message">
            <h2>✅ Analysis Complete!</h2>
            <p>Sent to your email: <strong>{st.session_state.book_title}</strong> by <strong>{st.session_state.author_name}</strong></p>
            <p>📧 Check your inbox (and spam)</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Analyze Another Book"):
            st.session_state.analysis_complete = False
            st.rerun()

def analyze_cover(cover_base64):
    """Cover analysis"""
    prompt = """Analyze this book cover. Return JSON with:
    {
        "colors": ["colors"],
        "mood": "feeling",
        "genre_signals": "genre",
        "strengths": ["strengths"],
        "weaknesses": ["weaknesses"]
    }"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cover_base64}"}}
                ]
            }],
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return None

def analyze_book_complete(text, cover_analysis, word_count):
    """Complete book analysis with clear scoring anchors"""
    
    if len(text) > 50000:
        text = text[:50000]
    
    # Extract title and author
    first_lines = text[:500].split('\n')
    title = "Unknown Title"
    author = "Unknown Author"
    
    for line in first_lines:
        if 'by' in line.lower() and len(line) < 50:
            author = line.replace('by', '').replace('BY', '').strip()
        elif line.strip() and len(line) > 3 and title == "Unknown Title":
            title = line.strip()
    
    # Get excerpts
    total_len = len(text)
    beginning = text[:min(4000, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:4000] if total_len > 10000 else ""
    ending = text[-4000:] if total_len > 5000 else ""
    
    cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis)}" if cover_analysis else ""
    
    prompt = f"""
    You are a literary analyst. Score this book based on the excerpts.
    
    SCORING GUIDE - USE THESE RANGES:
    85-95: Excellent - polished novel, strong plot, multiple characters, good dialogue
    75-84: Good - solid manuscript with minor issues
    60-74: Average - needs work
    40-59: Below average - amateur, needs significant revision
    Below 40: Poor - major problems
    
    Title: {title}
    Author: {author}
    Word count: {word_count}
    {cover_text}
    
    EXCERPTS:
    Beginning: {beginning}
    Middle: {middle}
    Ending: {ending}
    
    Return JSON with exactly this structure:
    {{
        "marketability": {{
            "overall_score": 0-100,
            "overall_grade": "A-F with +/-",
            "overall_assessment": "summary",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": "explanation"}},
                "commercial_potential": {{"score": 0-100, "explanation": "explanation"}},
                "genre_fit": {{"score": 0-100, "explanation": "explanation"}},
                "hook_strength": {{"score": 0-100, "explanation": "explanation"}},
                "character_appeal": {{"score": 0-100, "explanation": "explanation"}},
                "pacing": {{"score": 0-100, "explanation": "explanation"}},
                "originality": {{"score": 0-100, "explanation": "explanation"}}
            }}
        }},
        "writing_quality_detailed": {{
            "prose_quality": "",
            "dialogue": "",
            "description": "",
            "voice": "",
            "technical_execution": ""
        }},
        "book_info": {{
            "title": "{title}",
            "author": "{author}",
            "genre": "",
            "tone": "",
            "writing_style": "",
            "pacing_summary": ""
        }},
        "characters": {{
            "main": [],
            "supporting": []
        }},
        "narrative_arc": {{
            "exposition": "",
            "rising_action": "",
            "climax": "",
            "resolution": ""
        }},
        "strengths": [],
        "areas_for_improvement": [],
        "target_audience": {{
            "primary": "",
            "appeal": ""
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a literary analyst. Score honestly using the ranges provided."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        if 'book_info' not in result:
            result['book_info'] = {}
        result['book_info']['title'] = title
        result['book_info']['author'] = author
        return result
        
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        return None

def extract_text_full(file):
    """Extract text from file"""
    try:
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file)
            return " ".join([p.extract_text() for p in pdf_reader.pages])[:50000]
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            return " ".join([p.text for p in doc.paragraphs])[:50000]
        else:
            return file.getvalue().decode("utf-8")[:50000]
    except:
        return ""

if __name__ == "__main__":
    show_marketability_checker()
