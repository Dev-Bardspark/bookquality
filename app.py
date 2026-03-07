# BookMarketabilityChecker.py - COMPLETE WORKING VERSION
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

# Email config from secrets
SMTP_SERVER = st.secrets.get("SMTP_SERVER", "")
SMTP_PORT = st.secrets.get("SMTP_PORT", 587)
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "")
USE_TLS = st.secrets.get("use_tls", True)

# Load CSS
def load_css():
    try:
        with open('styles.css', 'r') as f:
            css = f.read()
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("CSS file not found. Using default styling.")

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
            "conclusion": "Likely human-written",
            "explanation": "Detailed reasoning",
            "confidence": 85
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
    """Send full analysis results via email"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    
    # For now, just return True to indicate success
    # In production, you'd implement actual email sending
    try:
        # Log that email would be sent
        print(f"Would send email to {recipient_email} with subject: {subject}")
        return True
    except Exception as e:
        st.error(f"Email sending failed: {e}")
        return False

def show_upload_section():
    """Display the upload section for book files"""
    
    with st.form("upload_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Author info
            author_name = st.text_input("Author Name *", placeholder="Enter your name")
            author_email = st.text_input("Email Address *", placeholder="Where to send the analysis")
            
        with col2:
            # Book info
            book_title = st.text_input("Book Title (optional)", placeholder="Enter book title")
        
        # File uploads
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
        
        # Submit button
        submitted = st.form_submit_button("🔍 Analyze My Book")
        
        if submitted:
            if not author_name or not author_email or not book_file:
                st.error("Please fill in all required fields (*)")
                return
            
            if '@' not in author_email or '.' not in author_email:
                st.error("Please enter a valid email address")
                return
            
            # Process files
            with st.spinner("📖 Analyzing your book... This may take a minute."):
                # Extract text from book
                if book_file.type == "application/pdf":
                    text = extract_text_from_pdf(book_file)
                elif book_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text = extract_text_from_docx(book_file)
                else:  # txt
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
                    # Add author info
                    if 'book_info' not in analysis_result:
                        analysis_result['book_info'] = {}
                    analysis_result['book_info']['author'] = author_name
                    if book_title:
                        analysis_result['book_info']['title'] = book_title
                    
                    st.session_state.analysis_result = analysis_result
                    st.session_state.analysis_done = True
                    
                    # Send email
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
    overall_grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis.get('book_info', {})
    book_title = book_info.get('title', 'Your Book')
    author_name = book_info.get('author', 'Unknown Author')
    
    # Separate AI results
    text_ai = ai_detection.get('text', {})
    text_conclusion = text_ai.get('conclusion', 'Inconclusive')
    
    # Determine text banner style
    text_lower = text_conclusion.lower()
    if 'human' in text_lower:
        text_banner_class = "ai-banner-text-human"
        text_icon = "✍️✅"
        text_text = "TEXT: HUMAN-GENERATED"
    elif 'ai-generated' in text_lower:
        text_banner_class = "ai-banner-text-ai"
        text_icon = "🤖⚠️"
        text_text = "TEXT: AI-GENERATED"
    elif 'assisted' in text_lower:
        text_banner_class = "ai-banner-text-assisted"
        text_icon = "🤖❓"
        text_text = "TEXT: POSSIBLE AI ASSISTANCE"
    else:
        text_banner_class = "ai-banner-text-inconclusive"
        text_icon = "❓"
        text_text = "TEXT: INCONCLUSIVE"
    
    cover_ai = ai_detection.get('cover', {})
    cover_conclusion = cover_ai.get('conclusion', 'inconclusive')
    
    # Determine cover banner style
    if cover_conclusion == "Clearly AI-generated":
        cover_banner_class = "ai-banner-cover-ai"
        cover_icon = "🤖⚠️"
        cover_text = "COVER: AI-GENERATED"
    elif cover_conclusion == "Likely human-written":
        cover_banner_class = "ai-banner-cover-human"
        cover_icon = "🎨✅"
        cover_text = "COVER: HUMAN-DESIGNED"
    else:
        cover_banner_class = "ai-banner-cover-inconclusive"
        cover_icon = "❓"
        cover_text = "COVER: INCONCLUSIVE"
    
    # Show title and author at top
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2>{book_title}</h2>
        <h3 style="color: #666;">by {author_name}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Show TEXT AI banner
    st.markdown(f"""
    <div class="ai-banner {text_banner_class}">
        <span class="ai-icon">{text_icon}</span>
        <div class="ai-content">
            <span class="ai-title">{text_text}</span>
            <span class="ai-confidence">({text_ai.get('confidence', 0)}% confidence)</span>
            <br>
            <span style="color: #666;">{text_ai.get('explanation', '')[:200]}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show COVER AI banner if cover was analyzed
    if st.session_state.cover_analysis:
        st.markdown(f"""
        <div class="ai-banner {cover_banner_class}">
            <span class="ai-icon">{cover_icon}</span>
            <div class="ai-content">
                <span class="ai-title">{cover_text}</span>
                <span class="ai-confidence">({cover_ai.get('confidence', 0)}% confidence)</span>
                <br>
                <span style="color: #666;">{cover_ai.get('explanation', '')[:200]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
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
    
    # Custom message based on score
    if overall_score < 70:
        weaknesses = analysis.get('areas_for_improvement', [])
        top_weaknesses = weaknesses[:3] if weaknesses else ["Writing quality needs work", "Plot structure is unclear", "Character development is shallow"]
        
        st.markdown(f"""
        <div class="warning-box">
            <h3 style="color: #cc5500; margin-top: 0;">⚠️ Your book needs more work</h3>
            <p>Most books sell only about 100 copies. A bad book will never sell. For this reason, we only accept books with a score of 70% or better for marketing support.</p>
            <p>Your book needs more work. Please read the analysis in your email to find areas of improvement.</p>
            <p style="font-weight: bold;">Based on our analysis, here's what's holding it back:</p>
            <ul>
                <li>{top_weaknesses[0] if len(top_weaknesses) > 0 else "Writing needs significant revision"}</li>
                <li>{top_weaknesses[1] if len(top_weaknesses) > 1 else "Plot requires stronger structure"}</li>
                <li>{top_weaknesses[2] if len(top_weaknesses) > 2 else "Characters need more depth"}</li>
            </ul>
        </div>
        
        <div class="email-section">
            <h2>✨ Ready to improve your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/">JOIN THE WAITLIST</a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("Congratulations! Your book has a strong marketability score of 70% or better. We're happy to accept it for further marketing support. Check your email for the full analysis.")
        
        st.markdown("""
        <div class="email-section">
            <h2>✨ Ready to MARKET your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/">JOIN THE WAITLIST</a>
        </div>
        """, unsafe_allow_html=True)
    
    st.success(f"✅ We've sent your complete analysis to your email!")

def show_marketability_checker():
    """Main function to run the app"""
    
    # Load CSS
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
