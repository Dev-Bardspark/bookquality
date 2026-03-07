# BookMarketabilityChecker.py - COMPLETE WORKING VERSION WITH EMAIL
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
import re
import tempfile
import os

# Page config must be first
st.set_page_config(
    page_title="Book Marketability Analyzer",
    page_icon="📚",
    layout="wide"
)

# Try to import the cover detector, but don't fail if it's not available
try:
    import ai_cover_detector_gpt4o_mini_png_only as ai_cover
    COVER_DETECTOR_AVAILABLE = True
except ImportError:
    COVER_DETECTOR_AVAILABLE = False
    st.warning("Cover AI detector module not found. Cover analysis will be limited.")

# Initialize OpenAI with secrets
if "OPENAI_API_KEY" in st.secrets:
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("OpenAI API key not found in secrets!")
    st.stop()

# Email config from secrets - USING YOUR WORKING SETTINGS
SMTP_SERVER = st.secrets["SMTP_SERVER"]  # "smtp.hostinger.com"
SMTP_PORT = st.secrets["SMTP_PORT"]      # 587
SENDER_EMAIL = st.secrets["SENDER_EMAIL"] # "dev@bardspark.com"
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"] # "AntEater1959*"
USE_TLS = st.secrets.get("use_tls", True)

# Editor email constant
EDITOR_EMAIL = "editor@bardspark.com"

# Load CSS
def load_css():
    try:
        with open('styles.css', 'r') as f:
            css = f.read()
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        # Default styling if CSS not found
        st.markdown("""
        <style>
        .stApp { background: #f5f5f5; }
        .main .block-container { background: white; border-radius: 20px; padding: 2rem; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .stButton > button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 25px; padding: 12px 30px; font-weight: 600; width: 100%; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; }
        </style>
        """, unsafe_allow_html=True)

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(docx_file):
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error extracting text from DOCX: {e}")
        return ""

def extract_text_from_txt(txt_file):
    """Extract text from TXT file"""
    try:
        return txt_file.getvalue().decode('utf-8')
    except Exception as e:
        st.error(f"Error extracting text from TXT: {e}")
        return ""

def analyze_cover(cover_file):
    """
    Full cover analysis
    """
    try:
        # Check file type
        if not cover_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.error("Please upload an image file (PNG, JPG, JPEG)")
            return None
        
        # Read the image
        image_bytes = cover_file.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Analyze cover design
        style_prompt = """Analyze this book cover's design elements. Return JSON with:
        {
            "colors": ["list of 3-5 dominant colors"],
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
        
        style_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": style_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{cover_file.type.split('/')[1]};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        style_result = json.loads(style_response.choices[0].message.content)
        
        # AI detection for cover (simplified)
        ai_detection = {
            "is_ai_generated": False,
            "verdict": "inconclusive",
            "confidence": 50,
            "indicators_found": [],
            "explanation": "Cover analysis completed"
        }
        
        # If the specialized detector is available, use it
        if COVER_DETECTOR_AVAILABLE:
            try:
                ai_detection_json = ai_cover.detect_ai_cover(image_bytes)
                ai_detection_result = json.loads(ai_detection_json)
                ai_detection = {
                    "is_ai_generated": ai_detection_result.get("verdict") == "likely_ai",
                    "verdict": ai_detection_result.get("verdict", "inconclusive"),
                    "confidence": ai_detection_result.get("confidence", 50),
                    "indicators_found": ai_detection_result.get("key_indicators", []),
                    "explanation": ai_detection_result.get("explanation", "")
                }
            except Exception as e:
                st.warning(f"Specialized AI detection failed, using basic analysis: {e}")
        
        # Combine both analyses
        result = {
            **style_result,
            "ai_detection": ai_detection
        }
        
        return result
        
    except Exception as e:
        st.error(f"Cover analysis failed: {e}")
        return None

def detect_ai_content(text, cover_analysis=None):
    """
    Analyze text and cover SEPARATELY for signs of AI generation
    """
    # Text detection prompt - balanced approach
    text_prompt = f"""
    You are an expert forensic AI text detector. Your analysis must be BALANCED and FAIR.
    
    IMPORTANT GUIDELINES:
    1. DO NOT flag polished, well-structured writing as AI. Many skilled human writers produce clean prose.
    2. DO NOT flag emotional content or inspirational themes as AI. Humans write about emotions too.
    3. DO NOT flag consistent tone as AI. Many authors maintain consistent voice throughout their work.
    4. Only flag text as AI if you find MULTIPLE clear, undeniable AI artifacts.
    5. When in doubt, err on the side of "Likely human-written" or "Inconclusive".
    
    MANUSCRIPT EXCERPT:
    {text[:10000]}
    
    ===== POSSIBLE AI INDICATORS (be very cautious with these) =====
    - Repetitive sentence structures that feel mechanical
    - Unnatural transitions between ideas
    - Generic descriptions that lack sensory details
    - Overuse of certain transition words (however, moreover, consequently)
    - Lack of personal voice or unique perspective
    
    ===== STRONG HUMAN INDICATORS (these are definitive proof) =====
    - Specific, quirky personal details or memories
    - Unique voice or writing style that feels authentic
    - Natural imperfections in rhythm or flow
    - Personal anecdotes with concrete details
    - Emotional authenticity that feels genuine
    
    ===== DECISION RULES =====
    - "Clearly AI-generated": Multiple undeniable AI patterns, NO human indicators
    - "Possibly AI-assisted": Some AI patterns but also some human elements
    - "Likely human-written": Clear human voice and authenticity, even if polished
    - "Inconclusive": Evidence is mixed or insufficient
    
    Return JSON with ONLY text analysis:
    {{
        "text_analysis": {{
            "indicators_found": [],
            "human_indicators_found": [],
            "conclusion": "string",
            "explanation": "string",
            "confidence": 0-100
        }}
    }}
    """
    
    try:
        text_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a fair and balanced forensic AI detector. 
                Your default assumption is that text is human-written unless you find overwhelming evidence otherwise.
                Professional human writing can be polished, emotional, and well-structured. Do not penalize quality."""},
                {"role": "user", "content": text_prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        text_result = json.loads(text_response.choices[0].message.content)["text_analysis"]
        
    except Exception as e:
        st.error(f"Text AI detection failed: {e}")
        text_result = {
            "indicators_found": [],
            "human_indicators_found": [],
            "conclusion": "Inconclusive",
            "explanation": "Text detection could not be completed",
            "confidence": 0
        }
    
    # Cover detection remains separate
    cover_result = {
        "indicators_found": [],
        "human_indicators_found": [],
        "conclusion": "Inconclusive",
        "explanation": "",
        "confidence": 0
    }
    
    if cover_analysis and 'ai_detection' in cover_analysis:
        ai_detect = cover_analysis['ai_detection']
        cover_result["indicators_found"] = ai_detect.get('indicators_found', [])
        
        # Map verdict to conclusion
        verdict = ai_detect.get('verdict', 'inconclusive')
        if verdict == "likely_ai":
            cover_result["conclusion"] = "Clearly AI-generated"
        elif verdict == "likely_human":
            cover_result["conclusion"] = "Likely human-written"
        else:
            cover_result["conclusion"] = "Inconclusive"
            
        cover_result["confidence"] = ai_detect.get('confidence', 0)
        cover_result["explanation"] = ai_detect.get('explanation', '')
        
        if verdict == "likely_human":
            cover_result["human_indicators_found"] = ["Professional design", "Consistent composition"]
    
    return {
        "text": text_result,
        "cover": cover_result
    }

def analyze_book_complete(text, cover_analysis=None):
    """Complete book analysis including marketability, writing quality, etc."""
    
    analysis_prompt = f"""
    You are an expert book editor and marketability analyst. Analyze this manuscript excerpt and provide detailed feedback.
    
    MANUSCRIPT EXCERPT:
    {text[:15000]}
    
    Return a comprehensive analysis in JSON format with the following structure:
    
    {{
        "book_info": {{
            "title": "Inferred title or 'Unknown'",
            "author": "Inferred author or 'Unknown'",
            "genres": ["primary genre", "secondary genre"],
            "tone": "overall tone of the book",
            "writing_style": "description of writing style",
            "pacing_summary": "description of pacing"
        }},
        
        "marketability": {{
            "overall_score": 0-100,
            "overall_grade": "A/B/C/D/F",
            "overall_assessment": "brief summary",
            "scores": {{
                "writing_quality": {{
                    "score": 0-100,
                    "explanation": "reasoning"
                }},
                "plot_structure": {{
                    "score": 0-100,
                    "explanation": "reasoning"
                }},
                "character_depth": {{
                    "score": 0-100,
                    "explanation": "reasoning"
                }},
                "commercial_appeal": {{
                    "score": 0-100,
                    "explanation": "reasoning"
                }},
                "market_originality": {{
                    "score": 0-100,
                    "explanation": "reasoning"
                }}
            }}
        }},
        
        "writing_quality_detailed": {{
            "prose_quality": "analysis",
            "dialogue": "analysis",
            "voice": "analysis"
        }},
        
        "characters": {{
            "main": [
                {{"name": "name", "role": "role", "description": "description"}}
            ]
        }},
        
        "plot": {{
            "opening_hook": "analysis",
            "inciting_incident": "analysis",
            "structure": "analysis"
        }},
        
        "themes": {{
            "primary": ["theme1", "theme2"]
        }},
        
        "target_audience": {{
            "primary": "description",
            "appeal": "what would appeal to them"
        }},
        
        "marketing": {{
            "unique_selling_points": ["point1", "point2"],
            "blurb_suggestion": "suggested blurb"
        }},
        
        "strengths": ["strength1", "strength2"],
        "areas_for_improvement": ["area1", "area2"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert book editor providing detailed, constructive feedback."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        st.error(f"Book analysis failed: {e}")
        return None

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, ai_detection_results):
    """Send full analysis results via email to user AND editor@bardspark.com"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    editor_subject = f"Book Analysis for {recipient_email}: {book_title} by {author_name}"
    
    # Get marketability score
    marketability = analysis_results.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    
    # Format the email body with FULL analysis
    book_info = analysis_results.get('book_info', {})
    
    # Get SEPARATE AI detection results
    text_ai = ai_detection_results.get('text', {})
    text_conclusion = text_ai.get('conclusion', 'Inconclusive')
    text_explanation = text_ai.get('explanation', '')
    text_confidence = text_ai.get('confidence', 0)
    text_indicators = text_ai.get('indicators_found', [])
    text_human_indicators = text_ai.get('human_indicators_found', [])
    
    cover_ai = ai_detection_results.get('cover', {})
    cover_conclusion = cover_ai.get('conclusion', 'inconclusive')
    cover_explanation = cover_ai.get('explanation', '')
    cover_confidence = cover_ai.get('confidence', 0)
    cover_indicators = cover_ai.get('indicators_found', [])
    cover_human_indicators = cover_ai.get('human_indicators_found', [])
    
    # Styling for TEXT AI
    text_lower = text_conclusion.lower()
    if 'human' in text_lower:
        text_bg = "#e8f5e8"
        text_border = "#4caf50"
        text_icon = "✍️✅"
        text_title = "TEXT: HUMAN-GENERATED"
        text_message = "The manuscript text appears authentically human-written"
        text_marketing_note = "Marketing Impact: Human-written quality builds authentic reader connections."
    elif 'ai-generated' in text_lower:
        text_bg = "#ffebee"
        text_border = "#f44336"
        text_icon = "🤖⚠️"
        text_title = "TEXT: AI-GENERATED"
        text_message = "The manuscript text shows strong signs of AI generation"
        text_marketing_note = "Marketing Impact: AI text may lack emotional depth; revise for unique voice."
    elif 'assisted' in text_lower:
        text_bg = "#fff3e0"
        text_border = "#ff9800"
        text_icon = "🤖❓"
        text_title = "TEXT: POSSIBLE AI ASSISTANCE"
        text_message = "The manuscript text may have used AI assistance"
        text_marketing_note = "Marketing Impact: Ensure unique voice to build reader loyalty."
    else:
        text_bg = "#f5f5f5"
        text_border = "#999999"
        text_icon = "❓"
        text_title = "TEXT: INCONCLUSIVE"
        text_message = "Text analysis could not determine clearly"
        text_marketing_note = "Marketing Impact: Get professional review for authenticity."

    # Styling for COVER AI
    if cover_conclusion == "Clearly AI-generated":
        cover_bg = "#ffebee"
        cover_border = "#f44336"
        cover_icon = "🤖⚠️"
        cover_title = "COVER: AI-GENERATED"
        cover_message = "The cover shows signs of AI generation"
        cover_marketing_note = "Marketing Impact: AI covers can look generic; consider professional redesign."
    elif cover_conclusion == "Likely human-written":
        cover_bg = "#e8f5e8"
        cover_border = "#4caf50"
        cover_icon = "🎨✅"
        cover_title = "COVER: HUMAN-DESIGNED"
        cover_message = "The cover appears human-designed"
        cover_marketing_note = "Marketing Impact: Professional covers attract more readers."
    else:
        cover_bg = "#f5f5f5"
        cover_border = "#999999"
        cover_icon = "❓"
        cover_title = "COVER: INCONCLUSIVE"
        cover_message = "Cover analysis could not determine clearly"
        cover_marketing_note = "Marketing Impact: Get feedback on cover design."

    # Build the email body
    body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center; }}
            .ai-section {{ padding: 20px; margin: 20px 0; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .ai-icon {{ font-size: 24px; margin-right: 10px; }}
            .ai-title {{ font-size: 18px; font-weight: bold; }}
            .indicator-list {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .marketing-impact {{ padding: 15px; border-radius: 8px; margin-top: 15px; }}
            .score-box {{ text-align: center; padding: 30px; background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); border-radius: 10px; margin: 20px 0; color: white; }}
            .score-number {{ font-size: 72px; font-weight: bold; margin: 0; line-height: 1; }}
            .score-label {{ font-size: 24px; margin: 10px 0 0; opacity: 0.9; }}
            .section {{ padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px; }}
            .warning-box {{ background: #fff3cd; border: 2px solid #ff8800; border-radius: 10px; padding: 30px; margin: 20px 0; }}
            .success-box {{ background: #d4edda; border: 2px solid #28a745; border-radius: 10px; padding: 30px; margin: 20px 0; }}
            .cta-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 30px; color: white; text-align: center; margin: 20px 0; }}
            .cta-button {{ background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0; opacity: 0.9;">by {author_name}</h3>
        </div>
        
        <!-- TEXT AI DETECTION SECTION -->
        <div class="ai-section" style="background: {text_bg}; border-left: 5px solid {text_border};">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{text_icon}</span>
                <div>
                    <span class="ai-title">{text_title}</span>
                    <span> ({text_confidence}% confidence)</span>
                </div>
            </div>
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {text_message}</p>
            <p style="color: #555;">{text_explanation}</p>
            
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">📝 Text Indicators:</p>
                {f'<p style="margin: 5px 0; color: #d32f2f;">⚠️ AI Indicators:</p><ul style="margin: 0 0 15px 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_indicators[:5]]) + '</ul>' if text_indicators else ''}
                {f'<p style="margin: 5px 0; color: #2e7d32;">✨ Human Qualities:</p><ul style="margin: 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_human_indicators[:3]]) + '</ul>' if text_human_indicators else ''}
            </div>
            
            <div class="marketing-impact" style="border-left: 3px solid {text_border}; background: rgba(255,255,255,0.7);">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0; color: #333;">{text_marketing_note}</p>
            </div>
        </div>
        
        <!-- COVER AI DETECTION SECTION -->
        {f'''
        <div class="ai-section" style="background: {cover_bg}; border-left: 5px solid {cover_border};">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{cover_icon}</span>
                <div>
                    <span class="ai-title">{cover_title}</span>
                    <span> ({cover_confidence}% confidence)</span>
                </div>
            </div>
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {cover_message}</p>
            <p style="color: #555;">{cover_explanation}</p>
            
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">🎨 Cover Indicators:</p>
                {f'<p style="margin: 5px 0; color: #d32f2f;">⚠️ AI Indicators:</p><ul style="margin: 0 0 15px 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_indicators[:5]]) + '</ul>' if cover_indicators else ''}
                {f'<p style="margin: 5px 0; color: #2e7d32;">✨ Human Qualities:</p><ul style="margin: 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_human_indicators[:3]]) + '</ul>' if cover_human_indicators else ''}
            </div>
            
            <div class="marketing-impact" style="border-left: 3px solid {cover_border}; background: rgba(255,255,255,0.7);">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0; color: #333;">{cover_marketing_note}</p>
            </div>
        </div>
        ''' if cover_analysis else ''}
        
        <!-- Marketability Score -->
        <div class="score-box">
            <p class="score-number">{overall_score}</p>
            <p class="score-label">Marketability Score</p>
        </div>
        
        <!-- Book Overview -->
        <div class="section">
            <h2>📖 Book Overview</h2>
            <p><strong>Genres:</strong> {', '.join(book_info.get('genres', ['Unknown']))}</p>
            <p><strong>Tone:</strong> {book_info.get('tone', 'Unknown')}</p>
            <p><strong>Writing Style:</strong> {book_info.get('writing_style', 'Unknown')}</p>
            <p><strong>Pacing:</strong> {book_info.get('pacing_summary', 'Unknown')}</p>
        </div>
        
        <!-- Overall Assessment -->
        <div class="section">
            <h2>📊 Overall Assessment</h2>
            <p>{marketability.get('overall_assessment', '')}</p>
        </div>
        
        <!-- Strengths & Improvements -->
        <div class="section">
            <h2>💪 Key Strengths</h2>
            <ul>
                {''.join([f'<li>{strength}</li>' for strength in analysis_results.get('strengths', [])[:5]])}
            </ul>
        </div>
        
        <div class="section">
            <h2>🔧 Areas for Improvement</h2>
            <ul>
                {''.join([f'<li>{area}</li>' for area in analysis_results.get('areas_for_improvement', [])[:5]])}
            </ul>
        </div>
        
        <!-- CTA Section -->
        {f'''
        <div class="warning-box">
            <h3 style="color: #cc5500; margin-top: 0;">⚠️ Your book needs more work</h3>
            <p>Most books sell only about 100 copies. A bad book will never sell. For this reason, we only accept books with a score of 70% or better for marketing support.</p>
            <p>Your book needs more work. Please use this analysis to find areas of improvement.</p>
        </div>
        ''' if overall_score < 70 else '''
        <div class="success-box">
            <h3 style="color: #28a745; margin-top: 0;">🎉 Congratulations!</h3>
            <p>Your book has a strong marketability score of 70% or better. We're happy to accept it for further marketing support.</p>
        </div>
        '''}
        
        <div class="cta-box">
            <h2>✨ Ready to market your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" class="cta-button">JOIN THE WAITLIST</a>
        </div>
        
        <p style="color: #999; font-size: 12px; text-align: center; margin-top: 30px;">
            Analysis performed on {datetime.now().strftime('%B %d, %Y')}
        </p>
    </body>
    </html>
    """
    
    try:
        # Connect to SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        if USE_TLS:
            server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Send to user
        user_msg = MIMEMultipart()
        user_msg['From'] = SENDER_EMAIL
        user_msg['To'] = recipient_email
        user_msg['Subject'] = subject
        user_msg.attach(MIMEText(body, 'html'))
        server.send_message(user_msg)
        
        # Send copy to editor
        editor_msg = MIMEMultipart()
        editor_msg['From'] = SENDER_EMAIL
        editor_msg['To'] = EDITOR_EMAIL
        editor_msg['Subject'] = editor_subject
        editor_msg.attach(MIMEText(body, 'html'))
        server.send_message(editor_msg)
        
        server.quit()
        return True
        
    except Exception as e:
        st.error(f"Email sending failed: {e}")
        return False

def show_upload_section():
    """Display the upload section for book files"""
    
    with st.form("upload_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            author_name = st.text_input("Author Name *", placeholder="Enter your name")
            author_email = st.text_input("Email Address *", placeholder="Where to send the analysis")
            
        with col2:
            book_title = st.text_input("Book Title (optional)", placeholder="Enter book title")
        
        st.markdown("### 📄 Upload Your Book")
        book_file = st.file_uploader(
            "Upload manuscript (PDF, DOCX, or TXT) *",
            type=['pdf', 'docx', 'txt'],
            help="Upload your book manuscript"
        )
        
        st.markdown("### 🎨 Upload Cover Image (Optional)")
        cover_file = st.file_uploader(
            "Upload cover image (PNG, JPG, JPEG)",
            type=['png', 'jpg', 'jpeg'],
            help="Upload your book cover for design analysis"
        )
        
        submitted = st.form_submit_button("🔍 Analyze My Book")
        
        if submitted:
            if not author_name or not author_email or not book_file:
                st.error("Please fill in all required fields (*)")
                return
            
            if '@' not in author_email or '.' not in author_email:
                st.error("Please enter a valid email address")
                return
            
            with st.spinner("📖 Analyzing your book... This may take a minute."):
                # Extract text from book
                if book_file.type == "application/pdf":
                    text = extract_text_from_pdf(book_file)
                elif book_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text = extract_text_from_docx(book_file)
                else:
                    text = extract_text_from_txt(book_file)
                
                if not text:
                    st.error("Could not extract text from the file. Please try another format.")
                    return
                
                # Analyze cover if provided
                cover_analysis = None
                if cover_file:
                    cover_analysis = analyze_cover(cover_file)
                    if cover_analysis:
                        st.session_state.cover_analysis = cover_analysis
                
                # Perform AI detection
                ai_detection = detect_ai_content(text, cover_analysis)
                st.session_state.ai_detection = ai_detection
                
                # Perform full book analysis
                analysis_result = analyze_book_complete(text, cover_analysis)
                
                if analysis_result:
                    if 'book_info' not in analysis_result:
                        analysis_result['book_info'] = {}
                    analysis_result['book_info']['author'] = author_name
                    if book_title:
                        analysis_result['book_info']['title'] = book_title
                    
                    st.session_state.analysis_result = analysis_result
                    st.session_state.analysis_done = True
                    
                    if send_email(author_email, analysis_result, cover_analysis, 
                                book_title or analysis_result['book_info'].get('title', 'Your Book'), 
                                author_name, ai_detection):
                        st.success("✅ Analysis complete! Check your email for the full report.")
                    else:
                        st.warning("Analysis complete but email could not be sent. Results shown below.")
                    
                    st.rerun()
                else:
                    st.error("Analysis failed. Please try again.")

def show_results_section():
    """Show results with separate text and cover AI banners"""
    
    analysis = st.session_state.analysis_result
    ai_detection = st.session_state.ai_detection
    marketability = analysis.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    book_info = analysis.get('book_info', {})
    book_title = book_info.get('title', 'Your Book')
    author_name = book_info.get('author', 'Unknown Author')
    
    # Show title
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2>{book_title}</h2>
        <h3 style="color: #666;">by {author_name}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Show score
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.metric("Marketability Score", f"{overall_score}/100")
    
    # Show AI results
    with st.expander("🤖 AI Detection Results", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            text_ai = ai_detection.get('text', {})
            text_conclusion = text_ai.get('conclusion', 'Inconclusive')
            text_confidence = text_ai.get('confidence', 0)
            
            if 'human' in text_conclusion.lower():
                st.success(f"📝 TEXT: {text_conclusion} ({text_confidence}%)")
            elif 'ai' in text_conclusion.lower():
                st.error(f"📝 TEXT: {text_conclusion} ({text_confidence}%)")
            else:
                st.warning(f"📝 TEXT: {text_conclusion} ({text_confidence}%)")
            
            st.write(text_ai.get('explanation', '')[:200])
        
        with col2:
            if st.session_state.cover_analysis:
                cover_ai = ai_detection.get('cover', {})
                cover_conclusion = cover_ai.get('conclusion', 'Inconclusive')
                cover_confidence = cover_ai.get('confidence', 0)
                
                if 'human' in cover_conclusion.lower():
                    st.success(f"🎨 COVER: {cover_conclusion} ({cover_confidence}%)")
                elif 'ai' in cover_conclusion.lower():
                    st.error(f"🎨 COVER: {cover_conclusion} ({cover_confidence}%)")
                else:
                    st.warning(f"🎨 COVER: {cover_conclusion} ({cover_confidence}%)")
                
                st.write(cover_ai.get('explanation', '')[:200])
    
    # Show CTA
    if overall_score < 70:
        st.warning("⚠️ Your book needs more work to reach a 70% marketability score.")
    else:
        st.success("🎉 Congratulations! Your book meets the 70% marketability threshold.")
    
    st.markdown("""
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://bardspark.com/sign-up-for-the-waitlist/" target="_blank">
            <button style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 15px 40px; border-radius: 25px; font-size: 18px; font-weight: bold; cursor: pointer;">
                🚀 Join BardSpark Waitlist
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True)

def show_marketability_checker():
    """Main function to run the app"""
    
    load_css()
    
    st.title("📚 Book Marketability Analyzer")
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <p style="font-size: 1.2rem; color: #666;">
            Get comprehensive analysis of your book's marketability, writing quality, and AI detection
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'analysis_done' not in st.session_state:
        st.session_state.analysis_done = False
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cover_analysis' not in st.session_state:
        st.session_state.cover_analysis = None
    if 'ai_detection' not in st.session_state:
        st.session_state.ai_detection = None
    
    # Show upload section
    show_upload_section()
    
    # Show results if analysis is done
    if st.session_state.analysis_done:
        show_results_section()
    
    # Footer
    st.markdown("""
    <div class="footer">
        <p>© 2024 BardSpark - Professional Book Analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_marketability_checker()
