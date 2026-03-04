# BookMarketabilityChecker.py - SIMPLIFIED ONE OPTION
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

def send_email(recipient_email, analysis_results, cover_analysis, book_title):
    """Send analysis results via email"""
    
    subject = f"Your Book Marketability Score: {book_title}"
    
    # Format the email body
    marketability = analysis_results.get('marketability', {})
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Book Marketability Score: {score} ({grade})</h1>
        </div>
        
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📊 Quick Overview</h2>
            <p>{marketability.get('overall_assessment', '')}</p>
        </div>
        
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📈 Detailed Scores</h2>
    """
    
    # Add scores
    scores = marketability.get('scores', {})
    for score_name, score_data in scores.items():
        display_name = score_name.replace('_', ' ').title()
        score_value = score_data.get('score', 0)
        explanation = score_data.get('explanation', '')
        body += f"""
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between;">
                    <strong>{display_name}</strong> <span>{score_value}</span>
                </div>
                <div style="height: 8px; background: #eee; border-radius: 4px;">
                    <div style="width: {score_value}%; height: 8px; background: #667eea; border-radius: 4px;"></div>
                </div>
                <p style="color: #666; font-size: 14px;">{explanation}</p>
            </div>
        """
    
    # Add cover analysis if available
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
    
    # Call to action
    body += f"""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Want the complete analysis?</h2>
            <p>Get full literary analysis, competitor comparison, and custom marketing plan.</p>
            <a href="https://yourapp.com/signup" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">SIGN UP FOR FULL ACCESS</a>
        </div>
        
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
    """Simple marketability checker for website homepage"""
    
    st.set_page_config(
        page_title="Is Your Book Ready to Sell?",
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
        .score-box {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            margin: 2rem 0;
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
        .feature-box {
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #667eea;
        }
        .signup-prompt {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin: 2rem 0;
        }
        .email-box {
            padding: 2rem;
            background: #f0f2f6;
            border-radius: 10px;
            margin: 2rem 0;
            border: 2px solid #667eea;
        }
        .free-badge {
            background: #00cc66;
            color: white;
            padding: 0.3rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: bold;
            display: inline-block;
            margin-left: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Is Your Book Ready to Sell?</h1>
        <p>Get your FREE marketability score in 60 seconds</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cover_analysis' not in st.session_state:
        st.session_state.cover_analysis = None
    if 'email_sent' not in st.session_state:
        st.session_state.email_sent = False
    
    # Show upload section if no analysis yet
    if not st.session_state.analysis_result:
        show_upload_section()
    else:
        show_results_section()

def show_upload_section():
    """Show file upload interface"""
    
    st.markdown("""
    <div class="feature-box">
        <h3>📤 Upload your manuscript <span class="free-badge">FREE</span></h3>
        <p>We'll analyze your entire manuscript (up to 50,000 characters) and email you the results.</p>
    </div>
    """, unsafe_allow_html=True)
    
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
            st.success(f"✅ {manuscript.name}")
    
    with col2:
        st.markdown("**🎨 Cover Image (optional)**")
        cover = st.file_uploader(
            "Upload JPG or PNG (optional)",
            type=['jpg', 'jpeg', 'png'],
            key="cover",
            label_visibility="collapsed"
        )
        if cover:
            st.success(f"✅ {cover.name}")
            image = Image.open(cover)
            st.image(image, width=100)
    
    # Email input
    st.markdown("---")
    st.markdown("### 📧 Where should we send your results?")
    
    email = st.text_input("Email address", placeholder="you@example.com")
    
    st.markdown("---")
    
    if manuscript and email:
        if st.button("🔍 GET MY FREE MARKETABILITY SCORE", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 60 seconds)"):
                
                # Extract full manuscript (capped at 50k chars)
                text = extract_text_full(manuscript, max_chars=50000)
                
                # Process cover if provided
                cover_analysis = None
                if cover:
                    cover_bytes = cover.getvalue()
                    cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
                    cover_analysis = analyze_cover_simple(cover_base64)
                    st.session_state.cover_analysis = cover_analysis
                
                # Analyze manuscript
                analysis = analyze_marketability(text, cover_analysis)
                
                # Get book title
                book_title = analysis.get('book_info', {}).get('title', 'Your Book')
                
                # Send email
                email_sent = send_email(email, analysis, cover_analysis, book_title)
                
                if email_sent:
                    st.session_state.analysis_result = analysis
                    st.session_state.email_sent = True
                    st.rerun()
                else:
                    st.error("Failed to send email. Please try again.")
    else:
        if not manuscript:
            st.info("👆 Please upload your manuscript")
        elif not email:
            st.info("👆 Please enter your email address")

def show_results_section():
    """Show success message and preview"""
    
    st.success("✅ Analysis complete! Check your email for the full results.")
    
    # Show preview
    analysis = st.session_state.analysis_result
    marketability = analysis.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    overall_grade = marketability.get('overall_grade', 'N/A')
    
    # Color based on score
    if overall_score >= 80:
        bg_color = "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
        emoji = "🚀"
    elif overall_score >= 70:
        bg_color = "linear-gradient(135deg, #f7971e 0%, #ffd200 100%)"
        emoji = "📈"
    elif overall_score >= 60:
        bg_color = "linear-gradient(135deg, #ff6b6b 0%, #feca57 100%)"
        emoji = "📊"
    else:
        bg_color = "linear-gradient(135deg, #ff4b4b 0%, #ff9f4b 100%)"
        emoji = "⚠️"
    
    # Show score
    st.markdown(f"""
    <div class="score-box" style="background: {bg_color};">
        <p class="score-number">{overall_score}</p>
        <p class="score-label">Marketability Score</p>
        <p style="font-size: 18px; margin-top: 10px;">Grade: {overall_grade} {emoji}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Call to action
    st.markdown("""
    <div class="signup-prompt">
        <h2>✨ Want more detailed insights?</h2>
        <p style="font-size: 18px;">Sign up for full access to:</p>
        <p>📖 Complete literary analysis</p>
        <p>🎨 Professional cover feedback</p>
        <p>📈 Competitor comparison</p>
        <p>🎯 Target audience breakdown</p>
        <p>📋 Custom marketing plan</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col2:
        if st.button("🚀 SIGN UP NOW", type="primary", use_container_width=True):
            st.markdown("[Click here to sign up](https://yourapp.com)")
    
    # Analyze another
    if st.button("🔄 Analyze Another Book", use_container_width=True):
        st.session_state.analysis_result = None
        st.session_state.cover_analysis = None
        st.session_state.email_sent = False
        st.rerun()

def analyze_cover_simple(cover_base64):
    """Simple cover analysis"""
    
    prompt = """Analyze this book cover briefly. Return JSON with:
    {
        "colors": ["list of dominant colors"],
        "has_figure": true/false,
        "mood": "emotional feeling",
        "genre_signals": "what genre this suggests",
        "strengths": ["2 specific strengths"],
        "weaknesses": ["2 specific weaknesses"],
        "suggestions": ["2 quick improvements"]
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
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except:
        return None

def analyze_marketability(text, cover_analysis):
    """Marketability analysis with gpt-4o-mini"""
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis, indent=2)}"
    
    # Truncate text if needed (API limits)
    if len(text) > 45000:
        text = text[:45000] + "... [truncated]"
    
    prompt = f"""
    Based on this manuscript, provide a marketability analysis.
    {cover_text}
    
    MANUSCRIPT:
    {text}
    
    Return JSON with:
    
    {{
        "marketability": {{
            "overall_score": (0-100 number),
            "overall_grade": ("A", "B", "C", "D", "F" with +/-),
            "overall_assessment": "One sentence summary",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": "brief"}},
                "commercial_potential": {{"score": 0-100, "explanation": "brief"}},
                "genre_fit": {{"score": 0-100, "explanation": "brief"}},
                "hook_strength": {{"score": 0-100, "explanation": "brief"}},
                "character_appeal": {{"score": 0-100, "explanation": "brief"}},
                "cover_effectiveness": {{"score": 0-100, "explanation": "brief"}}
            }}
        }},
        
        "book_info": {{
            "title": "detected title or suggestion",
            "genre": "primary genre",
            "tone": "overall tone"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a book market analyst. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return {
            "marketability": {
                "overall_score": 50,
                "overall_grade": "C",
                "overall_assessment": "Analysis failed. Please try again.",
                "scores": {}
            },
            "book_info": {
                "title": "Unknown",
                "genre": "Unknown",
                "tone": "Unknown"
            }
        }

def extract_text_full(file, max_chars=50000):
    """Extract entire manuscript up to max_chars"""
    try:
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text[:max_chars]
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text[:max_chars]
            
        else:  # txt
            text = file.getvalue().decode("utf-8")
            return text[:max_chars]
            
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# For running standalone
if __name__ == "__main__":
    show_marketability_checker()
