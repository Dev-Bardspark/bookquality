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
import re
import zipfile
from xml.etree import ElementTree
import fitz  # PyMuPDF for PDF cover extraction

# Initialize OpenAI with secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Email config from secrets
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = st.secrets["SMTP_PORT"]
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
USE_TLS = st.secrets.get("use_tls", True)

def estimate_pages_from_file_size(file_bytes, word_count=None):
    """Estimate number of pages based on file size and/or word count"""
    file_size_mb = len(file_bytes) / (1024 * 1024)
    
    # Rough estimates based on common formats:
    if word_count and word_count > 0:
        # If we have word count, use that (most accurate) - 300 words per page average
        pages = max(1, round(word_count / 300))
    else:
        # Fallback to file size estimation
        if file_size_mb < 0.1:  # Under 100KB
            pages = max(1, round(file_size_mb * 10))
        elif file_size_mb < 1:  # 100KB - 1MB
            pages = max(1, round(file_size_mb * 20))
        else:  # Over 1MB
            pages = max(1, round(file_size_mb * 30))
    
    return pages

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name):
    """Send full analysis results via email - SHOWS WORD COUNT ALWAYS"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    
    # Get word count from session state
    word_count = st.session_state.get('word_count', 0)
    estimated_pages = st.session_state.get('estimated_pages', 0)
    
    # Get marketability score to determine if signup message should show
    marketability = analysis_results.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    
    # Format the email body with FULL analysis
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0; opacity: 0.9;">by {author_name}</h3>
            <div style="font-size: 48px; font-weight: bold; margin: 20px 0;">{score} ({grade})</div>
            <p>Marketability Score</p>
        </div>
    """
    
    # WORD COUNT SECTION - ALWAYS SHOWS IN EMAIL
    body += f"""
        <div style="padding: 20px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 10px; margin: 20px 0;">
            <p style="color: #856404; margin: 0;"><strong>📊 Manuscript Stats:</strong> {word_count:,} words (~{estimated_pages} pages)</p>
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
        for char in chars.get('main', [])[:3]: # Top 3 characters
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
    
    # Plot Overview
    if 'plot' in analysis_results:
        plot = analysis_results['plot']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📊 Plot Analysis</h2>
            <p><strong>Opening Hook:</strong> {plot.get('opening_hook', '')}</p>
            <p><strong>Inciting Incident:</strong> {plot.get('inciting_incident', '')}</p>
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
    
    # Conditional signup message based on score with updated text and link
    if overall_score < 70:
        # Get weaknesses for warning message
        weaknesses = analysis_results.get('areas_for_improvement', [])
        top_weaknesses = weaknesses[:3] if weaknesses else ["Writing quality needs work", "Plot structure is unclear", "Character development is shallow"]
        
        body += f"""
        <div style="padding: 30px; background: #fff3cd; border: 2px solid #ff8800; border-radius: 10px; margin-top: 20px;">
            <h2 style="color: #cc5500; margin-top: 0;">⚠️ Your book needs more work</h2>
            <p>Most books sell only about 100 copies. A bad book will never sell. For this reason, we only accept books with a score of 70% or better for marketing support.</p>
            <p>Your book needs more work. Please use this analysis to find areas of improvement.</p>
            <p style="font-weight: bold;">Based on our analysis, here's what's holding it back:</p>
            <ul style="color: #856404;">
                <li>{top_weaknesses[0] if len(top_weaknesses) > 0 else "Writing needs significant revision"}</li>
                <li>{top_weaknesses[1] if len(top_weaknesses) > 1 else "Plot requires stronger structure"}</li>
                <li>{top_weaknesses[2] if len(top_weaknesses) > 2 else "Characters need more depth"}</li>
            </ul>
        </div>
        
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Ready to improve your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
        </div>
        """
    else:
        body += f"""
        <div style="padding: 30px; background: #00cc66; border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>🎉 Congratulations!</h2>
            <p style="font-size: 18px;">Your book has a strong marketability score of 70% or better. We're happy to accept it for further marketing support.</p>
        </div>
        
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Ready to MARKET your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
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
        # Send to user
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
        
        # Also send to editor with user's email in subject
        editor_msg = MIMEMultipart()
        editor_msg['From'] = SENDER_EMAIL
        editor_msg['To'] = "editor@bardspark.com"
        editor_msg['Subject'] = f"Book Analysis for {recipient_email}: {book_title}"
        editor_msg.attach(MIMEText(body, 'html'))
        server.send_message(editor_msg)
        
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
        - 📈 **Narrative arc** (exposition, rising action, climax, resolution)
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
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cover_analysis' not in st.session_state:
        st.session_state.cover_analysis = None
    if 'text' not in st.session_state:
        st.session_state.text = None
    if 'word_count' not in st.session_state:
        st.session_state.word_count = None
    if 'estimated_pages' not in st.session_state:
        st.session_state.estimated_pages = None
    
    if not st.session_state.analysis_complete:
        show_upload_section()
    else:
        show_results_section()

def show_upload_section():
    """Show file upload interface"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📄 Manuscript (required)**")
        manuscript = st.file_uploader(
            "Upload PDF, DOCX, DOC, ODT, RTF, or TXT",
            type=['pdf', 'docx', 'doc', 'odt', 'rtf', 'txt'],
            key="manuscript",
            label_visibility="collapsed"
        )
        if manuscript:
            st.success(f"✅ {manuscript.name}")
            
            # Get file bytes
            file_bytes = manuscript.getvalue()
            file_size_mb = len(file_bytes) / (1024 * 1024)
            
            # ESTIMATE word count based on file size (1MB ≈ 200,000 words for text)
            estimated_word_count = int(file_size_mb * 200000)
            
            # Ensure minimum reasonable count
            if estimated_word_count < 1000:
                estimated_word_count = 1000
                
            st.session_state.word_count = estimated_word_count
            
            # Extract text for analysis (truncated)
            st.session_state.text = extract_text_for_analysis(manuscript)
            
            # Estimate pages
            estimated_pages = estimate_pages_from_file_size(file_bytes, estimated_word_count)
            st.session_state.estimated_pages = estimated_pages
            
            # WORD COUNT SHOWS HERE ON SCREEN
            st.info(f"Your manuscript is approximately {estimated_word_count:,} words based on file size (~{estimated_pages} pages). A typical novel ranges from 70,000 to 100,000 words. Note: If this is a partial manuscript or work in progress, the analysis will still be performed on the provided content without penalizing the score for length.")
    
    with col2:
        st.markdown("**🎨 Cover Image (optional but recommended)**")
        cover = st.file_uploader(
            "Upload JPG, PNG, GIF, WEBP, BMP, TIFF, or PDF",
            type=['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'tif', 'pdf'],
            key="cover",
            label_visibility="collapsed"
        )
        if cover:
            st.success(f"✅ {cover.name}")
            # For PDF covers, show a note but don't try to display
            if cover.type == "application/pdf":
                st.info("📄 PDF cover uploaded (will be analyzed)")
            else:
                try:
                    image = Image.open(cover)
                    st.image(image, width=100)
                except:
                    st.info(f"✅ {cover.name} uploaded")
    
    # Optional title and author inputs to override detection
    book_title = st.text_input("Book Title (optional - we'll try to detect it if not provided)", "")
    author_name = st.text_input("Author Name (optional - we'll try to detect it if not provided)", "")
    
    st.markdown("---")
    st.markdown("### 📧 Where should we send your complete analysis?")
    
    email = st.text_input("Email address", placeholder="you@example.com", key="recipient_email")
    
    # Small "no spam" text under email
    st.markdown("""
    <p style="font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 20px;">
        We'll never spam you. Just this one analysis.
    </p>
    """, unsafe_allow_html=True)
    
    if manuscript and email:
        # ALWAYS reset for new analysis
        st.session_state.analysis_complete = False
        st.session_state.analysis_result = None
        st.session_state.cover_analysis = None
        
        if st.button("🔍 GET MY FREE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 60 seconds)"):
                       
                # Use pre-extracted text
                text = st.session_state.text
                
                # Process cover if provided
                cover_analysis = None
                if cover:
                    cover_analysis = analyze_cover(cover)
                    st.session_state.cover_analysis = cover_analysis
                
                # Analyze manuscript (FULL analysis)
                analysis = analyze_book_complete(text, cover_analysis, book_title, author_name)
                
                if analysis:
                    st.session_state.analysis_result = analysis
                    
                    # Get book title and author (use provided or detected)
                    book_info = analysis.get('book_info', {})
                    final_title = book_info.get('title', 'Your Book')
                    final_author = book_info.get('author', 'Unknown Author')
                    
                    # Send email
                    email_sent = send_email(email, analysis, cover_analysis, final_title, final_author)
                    
                    if email_sent:
                        st.session_state.analysis_complete = True
                        st.session_state.book_title = final_title
                        st.session_state.author_name = final_author
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

def show_results_section():
    """Show results with preview and low score warning if needed"""
    
    analysis = st.session_state.analysis_result
    marketability = analysis.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    overall_grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis.get('book_info', {})
    book_title = book_info.get('title', 'Your Book')
    author_name = book_info.get('author', 'Unknown Author')
    
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
    
    # Show title and author at top
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2>{book_title}</h2>
        <h3 style="color: #666;">by {author_name}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Show score
    st.markdown(f"""
    <div class="score-box" style="background: {bg_color};">
        <p class="score-number">{overall_score}</p>
        <p class="score-label">Marketability Score</p>
        <p style="font-size: 18px; margin-top: 10px;">Grade: {overall_grade} {emoji}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Custom message based on score with updated text and link
    if overall_score < 70:
        # Get specific weaknesses to show
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
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin: 20px 0; color: white; text-align: center;">
            <h2>✨ Ready to improve your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("Congratulations! Your book has a strong marketability score of 70% or better. We're happy to accept it for further marketing support. Check your email for the full analysis.")
        
        st.markdown("""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin: 20px 0; color: white; text-align: center;">
            <h2>✨ Ready to MARKET your book?</h2>
            <p style="font-size: 18px;">Sign up for BardSpark to access:</p>
            <p>🔍 ARC reader & influencer finder</p>
            <p>🎨 Marketing asset generator</p>
            <p>📊 Competitor tracker</p>
            <p>🎬 BookTok video creator</p>
            <p>🌐 Author website builder</p>
            <p>And Much More</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
        </div>
        """, unsafe_allow_html=True)
    
    st.success(f"✅ We've sent your complete analysis to your email!")

def analyze_cover(cover_file):
    """Full cover analysis - handles PDFs using PyMuPDF and all image formats"""
    
    try:
        # Handle PDF files with PyMuPDF
        if cover_file.type == "application/pdf":
            st.info("🔄 Analyzing PDF cover...")
            
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(stream=cover_file.getvalue(), filetype="pdf")
            
            # Get first page
            first_page = pdf_document[0]
            
            # Render page to image (higher dpi = better quality)
            zoom = 2.0  # 2x zoom for better quality
            mat = fitz.Matrix(zoom, zoom)
            pix = first_page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to bytes
            img_bytes = pix.tobytes("png")
            cover_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            pdf_document.close()
            
        else:
            # Handle regular image formats
            cover_bytes = cover_file.getvalue()
            cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
        
        # Analyze with OpenAI vision
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
        
    except Exception as e:
        st.error(f"Cover analysis failed: {e}")
        return None

def extract_text_for_analysis(file):
    """Extract text for analysis only - simplified version"""
    try:
        file_bytes = file.getvalue()
        
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages[:20]:  # First 20 pages for analysis
                text += page.extract_text() + "\n"
            return text[:50000]
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = ""
            for para in doc.paragraphs[:1000]:  # First 1000 paragraphs for analysis
                text += para.text + "\n"
            return text[:50000]
            
        elif file.type == "application/vnd.oasis.opendocument.text":
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as odt_zip:
                    with odt_zip.open('content.xml') as xml_file:
                        tree = ElementTree.parse(xml_file)
                        root = tree.getroot()
                        namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
                        text_parts = []
                        for elem in root.findall('.//text:p', namespaces)[:500]:
                            if elem.text:
                                text_parts.append(elem.text)
                        return ' '.join(text_parts)[:50000]
            except:
                return file_bytes.decode("utf-8", errors="ignore")[:50000]
        
        elif file.type == "application/rtf" or file.type == "text/rtf" or file.name.endswith('.rtf'):
            content = file_bytes.decode("utf-8", errors="ignore")
            text = re.sub(r'\\[a-z]+[0-9-]*', ' ', content)
            text = re.sub(r'\{[^}]*\}', ' ', text)
            text = re.sub(r'\\\'[0-9a-f]{2}', ' ', text)
            return ' '.join(text.split())[:50000]
        
        elif file.type == "application/msword":
            return file_bytes.decode("utf-8", errors="ignore")[:50000]
        
        else:  # Plain text
            return file_bytes.decode("utf-8", errors="ignore")[:50000]
            
    except Exception as e:
        st.error(f"Error extracting text for analysis: {e}")
        return ""

def analyze_book_complete(text, cover_analysis, provided_title="", provided_author=""):
    """Complete book analysis based on ACTUAL manuscript text"""
    
    if len(text) > 50000:
        text = text[:50000] + "... [truncated]"
    
    total_len = len(text)
    beginning = text[:min(5000, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:5000]
    ending = text[-5000:]
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis, indent=2)}"
    
    # Extract title and author from first few lines if not provided
    if provided_title and provided_author:
        detected_title = provided_title
        detected_author = provided_author
    else:
        first_lines = [line.strip() for line in text[:1000].split('\n') if line.strip()]
        detected_title = "Unknown Title"
        detected_author = "Unknown Author"
        
        for i, line in enumerate(first_lines):
            if re.match(r'https?://', line) or len(line) < 5:
                continue
            if i == 0:
                detected_title = line
            if 'by' in line.lower() and len(line) < 100:
                detected_author = re.sub(r'(?i)by', '', line).strip()
                break
        if detected_author == "Unknown Author" and len(first_lines) > 1:
            detected_author = first_lines[1] if len(first_lines[1]) < 50 else "Unknown Author"
    
    prompt = f"""
    You are a professional literary analyst. Analyze THIS SPECIFIC BOOK based SOLELY on the manuscript excerpts provided below.
    
    BOOK TITLE (detected from manuscript): {detected_title}
    AUTHOR (detected from manuscript): {detected_author}
    
    {cover_text}
    
    ACTUAL MANUSCRIPT EXCERPTS - USE THESE FOR YOUR ANALYSIS:
    
    BEGINNING (first 5000 chars):
    {beginning}
    
    MIDDLE (middle 5000 chars):
    {middle}
    
    ENDING (last 5000 chars):
    {ending}
    
    IMPORTANT INSTRUCTIONS:
    1. The book title MUST be "{detected_title}" in your response
    2. The author MUST be "{detected_author}" in your response
    3. Base ALL scores and comments on the ACTUAL text above
    4. For characters: You MUST identify ALL characters mentioned in the excerpts. For each main character, include:
       - Their name
       - Their role (protagonist, antagonist, deuteragonist, confidant, foil, love interest, mentor, etc.)
       - Description of who they are
       - How they change (if shown)
       - What drives them
       - Their internal or external struggles
       - Why readers will connect with them
    5. Include supporting characters and key relationships between characters
    6. For character_development section, describe how the protagonist evolves, what motivates any antagonist, and how supporting characters change
    7. For narrative arc: describe what you actually see in these excerpts
    8. Be specific - reference actual events, names, and details from the text
    9. For areas_for_improvement: be honest about weaknesses in THIS text
    
    Return JSON with these sections:
    
    {{
        "marketability": {{
            "overall_score": (0-100 number based on these excerpts),
            "overall_grade": ("A", "B", "C", "D", "F" with +/-),
            "overall_assessment": "One sentence summary of this specific book",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": "Based on the prose in these excerpts - be specific"}},
                "commercial_potential": {{"score": 0-100, "explanation": "Based on the hook and content shown"}},
                "genre_fit": {{"score": 0-100, "explanation": "How well this matches genre conventions"}},
                "hook_strength": {{"score": 0-100, "explanation": "Based on the opening excerpt"}},
                "character_appeal": {{"score": 0-100, "explanation": "Based on characters shown in excerpts"}},
                "pacing": {{"score": 0-100, "explanation": "Based on flow between beginning, middle, and end"}},
                "originality": {{"score": 0-100, "explanation": "Unique elements observed in these excerpts"}}
            }}
        }},
        
        "writing_quality_detailed": {{
            "prose_quality": "Assessment of sentence-level writing from these excerpts - quote examples",
            "dialogue": "Quality and naturalness of dialogue from these excerpts - quote examples",
            "description": "Quality of descriptive passages from these excerpts - quote examples",
            "voice": "Strength and consistency of narrative voice in these excerpts",
            "technical_execution": "Grammar, punctuation, formatting in these excerpts"
        }},
        
        "book_info": {{
            "title": "{detected_title}",
            "author": "{detected_author}",
            "genre": "primary genre based on content",
            "subgenres": ["subgenre1", "subgenre2"],
            "tone": "overall emotional tone from these excerpts",
            "writing_style": "descriptive/lyrical/direct/etc from these excerpts",
            "pacing_summary": "fast/medium/slow based on these excerpts"
        }},
        
        "characters": {{
            "main": [
                {{
                    "name": "character name",
                    "role": "protagonist/antagonist/etc",
                    "description": "who they are based on excerpts",
                    "arc": "how they change (if shown)",
                    "motivation": "what drives them (if shown)",
                    "conflict": "internal or external struggles (if shown)",
                    "appeal_factor": "Why readers will connect with this character"
                }}
            ],
            "supporting": ["list of supporting characters mentioned"],
            "relationships": ["key dynamics between characters shown or implied"]
        }},
        
        "character_development": {{
            "protagonist_journey": "how the main character changes based on excerpts",
            "antagonist_motivation": "what drives the opposition (if present)",
            "supporting_arcs": ["how other characters evolve (if shown)"]
        }},
        
        "narrative_arc": {{
            "exposition": "setup shown in beginning excerpt",
            "rising_action": "events in middle excerpt",
            "climax": "turning point in excerpts (if any)",
            "falling_action": "aftermath in ending excerpt (if any)",
            "resolution": "conclusion shown in ending excerpt"
        }},
        
        "plot": {{
            "opening_hook": "what grabs attention in the first 500 chars",
            "inciting_incident": "what starts the story (if shown)",
            "major_plot_points": ["point1 from excerpts", "point2 from excerpts"],
            "plot_twists": ["any surprises in excerpts"]
        }},
        
        "themes": {{
            "primary": ["main themes visible in excerpts"],
            "secondary": ["other themes hinted at"]
        }},
        
        "strengths": ["5 specific strengths of THIS manuscript with examples from the text"],
        
        "areas_for_improvement": ["5 specific weaknesses in THIS manuscript with concrete suggestions based on the text"],
        
        "target_audience": {{
            "primary": "who would enjoy THIS specific book",
            "appeal": "why they'd enjoy it based on these excerpts"
        }},
        
        "marketing": {{
            "unique_selling_points": ["what makes THIS specific book special based on excerpts"],
            "blurb_suggestion": "A potential back-cover blurb based on THIS content"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a literary analyst. Return valid JSON only. Base your analysis strictly on the provided excerpts."},
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

# For running standalone
if __name__ == "__main__":
    show_marketability_checker()
