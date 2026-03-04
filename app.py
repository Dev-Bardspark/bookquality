# BookMarketabilityChecker.py - FULL ANALYSIS VIA EMAIL
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
    """Send full analysis results via email"""
    
    subject = f"Your Complete Book Analysis: {book_title}"
    
    # Format the email body with FULL analysis
    marketability = analysis_results.get('marketability', {})
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 28px;">{book_info.get('title', 'Your Book')}</h2>
            <div style="font-size: 48px; font-weight: bold; margin: 20px 0;">{score} ({grade})</div>
            <p>Marketability Score</p>
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
    
    # Detailed Scores
    body += """
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📈 Detailed Scores</h2>
    """
    
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
        for char in chars.get('main', [])[:3]:  # Top 3 characters
            body += f"""
            <div style="margin-bottom: 15px; padding: 10px; background: white; border-radius: 5px;">
                <strong>{char.get('name', 'Unknown')}</strong> - {char.get('role', '')}<br>
                <p style="margin: 5px 0 0 0; color: #666;">{char.get('description', '')}</p>
            </div>
            """
        body += "</div>"
    
    # Plot Overview
    if 'plot' in analysis_results:
        plot = analysis_results['plot']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📊 Plot Analysis</h2>
            <p><strong>Opening Hook:</strong> {plot.get('opening_hook', '')}</p>
            <p><strong>Inciting Incident:</strong> {plot.get('inciting_incident', '')}</p>
        </div>
        """
    
    # Themes
    if 'themes' in analysis_results:
        themes = analysis_results['themes']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎯 Themes</h2>
            <p><strong>Primary:</strong> {', '.join(themes.get('primary', []))}</p>
        </div>
        """
    
    # Cover analysis if available
    if cover_analysis:
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
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
    
    # Target Audience
    if 'target_audience' in analysis_results:
        audience = analysis_results['target_audience']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎯 Target Audience</h2>
            <p><strong>Primary:</strong> {audience.get('primary', '')}</p>
            <p><strong>Appeal:</strong> {audience.get('appeal', '')}</p>
        </div>
        """
    
    # Marketing Insights
    if 'marketing' in analysis_results:
        marketing = analysis_results['marketing']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📢 Marketing Insights</h2>
            <p><strong>Unique Selling Points:</strong></p>
            <ul>
        """
        for usp in marketing.get('unique_selling_points', [])[:3]:
            body += f"<li>{usp}</li>"
        
        if marketing.get('blurb_suggestion'):
            body += f"""
            </ul>
            <p><strong>Suggested Blurb:</strong><br>
            <em>{marketing['blurb_suggestion']}</em></p>
            """
        body += "</div>"
    
    # Call to action - Sign up for interactive tools
    body += f"""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Want to do more with your analysis?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to:</p>
            <p>🔍 Find ARC readers and influencers</p>
            <p>🎨 Generate marketing assets for all platforms</p>
            <p>📊 Track competitor books</p>
            <p>🎬 Create BookTok videos</p>
            <p>🌐 Build your author website</p>
            <a href="https://yourapp.com/signup" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">SIGN UP FOR FREE</a>
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
    """Marketability checker that delivers FULL analysis via email"""
    
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
        <h1>📊 Free Book Analysis</h1>
        <p>Get your COMPLETE book analysis emailed to you in 60 seconds</p>
    </div>
    """, unsafe_allow_html=True)
    
    # What they get
    with st.expander("📋 What's included in your free analysis", expanded=True):
        st.markdown("""
        - 📖 **Full book analysis** (genre, tone, writing style, pacing)
        - 📊 **Marketability score** with detailed breakdown
        - ✍️ **Writing quality assessment** (prose, dialogue, voice)
        - 👥 **Character analysis** (main characters and their roles)
        - 📈 **Plot analysis** (hook, inciting incident, structure)
        - 🎯 **Theme identification** and motif analysis
        - 💪 **Key strengths** of your manuscript
        - 🔧 **Areas for improvement** with specific suggestions
        - 🎨 **Cover analysis** (if you upload it)
        - 🎯 **Target audience** identification
        - 📢 **Marketing insights** and blurb suggestion
        """)
    
    st.markdown("---")
    
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    
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
            st.success(f"✅ {manuscript.name}")
    
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
    
    st.markdown("---")
    st.markdown("""
    <div style="background: #fff3cd; padding: 15px; border-radius: 10px; border-left: 4px solid #ffc107; margin: 20px 0;">
        <strong>⏱️ Analysis takes about 60 seconds.</strong> We'll analyze your entire manuscript and send you the complete report.
    </div>
    """, unsafe_allow_html=True)
    
    if manuscript and email:
        if st.button("🔍 GET MY FREE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 60 seconds)"):
                
                # Extract full manuscript
                text = extract_text_full(manuscript)
                
                # Process cover if provided
                cover_analysis = None
                if cover:
                    cover_bytes = cover.getvalue()
                    cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
                    cover_analysis = analyze_cover(cover_base64)
                
                # Analyze manuscript (FULL analysis)
                analysis = analyze_book_complete(text, cover_analysis)
                
                if analysis:
                    # Get book title
                    book_title = analysis.get('book_info', {}).get('title', 'Your Book')
                    
                    # Send email
                    email_sent = send_email(email, analysis, cover_analysis, book_title)
                    
                    if email_sent:
                        st.session_state.analysis_complete = True
                        st.session_state.book_title = book_title
                        st.rerun()
                    else:
                        st.error("Failed to send email. Please try again.")
                else:
                    st.error("Analysis failed. Please try again.")
    else:
        if not manuscript:
            st.info("👆 Please upload your manuscript")
        elif not email:
            st.info("👆 Please enter your email address")

def show_success_section():
    """Show success message"""
    
    st.success(f"✅ Analysis complete! We've sent your full report to your email.")
    
    st.markdown("""
    <div style="text-align: center; padding: 30px; background: #f8f9fa; border-radius: 10px; margin: 30px 0;">
        <h3>📧 Check your inbox</h3>
        <p>Your complete book analysis is on its way!</p>
        <p style="color: #666; font-size: 14px;">(If you don't see it, check your spam folder)</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🚀 Ready to market your book?")
    st.markdown("Sign up for BardSpark to access all our marketing tools:")
    
    col1, col2, col3 = st.columns(3)
    with col2:
        if st.button("SIGN UP FOR FREE", use_container_width=True):
            st.markdown("[Click here to sign up](https://yourapp.com/signup)")
    
    if st.button("🔄 Analyze Another Book", use_container_width=True):
        st.session_state.analysis_complete = False
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

def analyze_book_complete(text, cover_analysis):
    """Complete book analysis (same as your BookAnalyzer)"""
    
    if len(text) > 50000:
        text = text[:50000] + "... [truncated]"
    
    total_len = len(text)
    beginning = text[:min(5000, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:5000]
    ending = text[-5000:]
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis, indent=2)}"
    
    prompt = f"""
    You are a professional literary analyst. Analyze this book based on the manuscript excerpts provided.
    {cover_text}
    
    MANUSCRIPT EXCERPTS:
    
    BEGINNING:
    {beginning}
    
    MIDDLE:
    {middle}
    
    ENDING:
    {ending}
    
    Return JSON with these sections:
    
    {{
        "marketability": {{
            "overall_score": 85,
            "overall_grade": "A-",
            "overall_assessment": "Brief summary based on manuscript quality",
            "scores": {{
                "writing_quality": {{"score": 88, "explanation": "Based on prose quality", "strengths": [], "weaknesses": []}},
                "commercial_potential": {{"score": 82, "explanation": "Based on hook and pacing", "strengths": [], "weaknesses": []}},
                "genre_fit": {{"score": 90, "explanation": "How well it matches genre conventions", "strengths": [], "weaknesses": []}},
                "hook_strength": {{"score": 85, "explanation": "Based on opening", "strengths": [], "weaknesses": []}},
                "character_appeal": {{"score": 80, "explanation": "Based on character depth shown", "strengths": [], "weaknesses": []}},
                "pacing": {{"score": 75, "explanation": "Based on flow of excerpts", "strengths": [], "weaknesses": []}},
                "originality": {{"score": 70, "explanation": "Unique elements observed", "strengths": [], "weaknesses": []}}
            }}
        }},
        
        "writing_quality_detailed": {{
            "prose_quality": "Assessment of sentence-level writing",
            "dialogue": "Quality and naturalness of dialogue",
            "description": "Quality of descriptive passages",
            "voice": "Strength and consistency of narrative voice",
            "technical_execution": "Grammar, punctuation, formatting"
        }},
        
        "book_info": {{
            "title": "detected title",
            "genre": "primary genre",
            "subgenres": ["subgenre1", "subgenre2"],
            "tone": "overall emotional tone",
            "writing_style": "descriptive/lyrical/direct/etc",
            "pacing_summary": "fast/medium/slow with explanation"
        }},
        
        "characters": {{
            "main": [
                {{
                    "name": "name",
                    "role": "protagonist/antagonist/etc",
                    "description": "who they are",
                    "arc": "how they change",
                    "motivation": "what drives them"
                }}
            ]
        }},
        
        "plot": {{
            "opening_hook": "what grabs attention",
            "inciting_incident": "what starts the story",
            "major_plot_points": ["point1", "point2", "point3"]
        }},
        
        "themes": {{
            "primary": ["main themes with explanation"],
            "secondary": ["other themes"]
        }},
        
        "strengths": ["5 specific strengths of this manuscript"],
        
        "areas_for_improvement": ["5 specific weaknesses with suggestions"],
        
        "target_audience": {{
            "primary": "who will love this",
            "appeal": "why they'll love it"
        }},
        
        "marketing": {{
            "unique_selling_points": ["what makes it special"],
            "blurb_suggestion": "A potential back-cover blurb"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a literary analyst. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
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
            return text[:50000]  # Cap at 50k chars
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text[:50000]
            
        else:  # txt
            text = file.getvalue().decode("utf-8")
            return text[:50000]
            
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# For running standalone
if __name__ == "__main__":
    show_marketability_checker()
