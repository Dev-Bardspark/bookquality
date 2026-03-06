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

def detect_ai_content(text, cover_analysis=None):
    """
    Analyze text and cover for signs of AI generation
    Returns: dict with detection results
    """
    # Convert cover_analysis to a string for the prompt
    cover_text = "No cover provided"
    cover_ai_info = ""
    
    if cover_analysis:
        cover_text = json.dumps(cover_analysis, indent=2)
        # Extract AI detection from cover analysis if available
        if 'ai_detection' in cover_analysis:
            ai_detect = cover_analysis['ai_detection']
            cover_ai_info = f"""
            COVER AI DETECTION RESULTS:
            AI Generated: {ai_detect.get('is_ai_generated', 'unknown')}
            Confidence: {ai_detect.get('confidence', 0)}%
            Indicators: {ai_detect.get('indicators_found', [])}
            Explanation: {ai_detect.get('explanation', '')}
            """
    
    prompt = f"""
    Analyze this book manuscript excerpt and cover analysis for signs of AI generation.
    
    MANUSCRIPT EXCERPT:
    {text[:10000]}  # First 10,000 chars for analysis
    
    COVER ANALYSIS:
    {cover_text}
    
    {cover_ai_info}
    
    Look for these AI indicators:
    
    TEXT INDICATORS:
    - Overuse of common AI transition phrases ("Furthermore", "Moreover", "In conclusion", "It is important to note")
    - Repetitive sentence structures
    - Generic descriptions lacking specific sensory details
    - Predictable dialogue patterns
    - Lack of authentic voice or personality
    - Hallucinated facts or inconsistencies
    - Too "perfect" grammar with no stylistic quirks
    
    COVER INDICATORS (from the cover analysis above):
    - Use the cover AI detection results if available
    - Pay special attention to text gibberish, hand/finger anomalies, lighting inconsistencies
    
    Return JSON with:
    {{
        "text_analysis": {{
            "indicators_found": ["list of specific AI signs in the text - if none, leave empty"],
            "human_indicators_found": ["list of human-written signs - e.g., 'unique voice', 'emotional depth', 'specific sensory details']
        }},
        "cover_analysis": {{
            "indicators_found": ["list of AI signs in cover - USE THE COVER AI DETECTION RESULTS"],
            "human_indicators_found": ["list of human-designed signs in cover - e.g., 'thoughtful composition', 'consistent lighting']
        }},
        "overall_assessment": {{
            "conclusion": ONE OF THESE EXACT PHRASES: "Likely human-written", "Possibly AI-assisted", "Clearly AI-generated", or "Inconclusive",
            "explanation": "Brief explanation of the determination including both text and cover analysis if available"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI detection expert. Analyze the text and cover and return your conclusion using ONLY one of these exact phrases: 'Likely human-written', 'Possibly AI-assisted', 'Clearly AI-generated', or 'Inconclusive'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI detection failed: {e}")
        return {
            "overall_assessment": {
                "conclusion": "Inconclusive",
                "explanation": "AI detection could not be completed"
            }
        }

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, ai_detection_results):
    """Send full analysis results via email with AI detection"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    
    # Get marketability score
    marketability = analysis_results.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    
    # Format the email body with FULL analysis
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
    
    # Get AI detection results
    ai_overall = ai_detection_results.get('overall_assessment', {})
    ai_conclusion = ai_overall.get('conclusion', 'Inconclusive')
    ai_explanation = ai_overall.get('explanation', '')
    
    # Get text indicators
    text_indicators = ai_detection_results.get('text_analysis', {}).get('indicators_found', [])
    text_human_indicators = ai_detection_results.get('text_analysis', {}).get('human_indicators_found', [])
    
    # Get cover indicators
    cover_indicators = ai_detection_results.get('cover_analysis', {}).get('indicators_found', [])
    cover_human_indicators = ai_detection_results.get('cover_analysis', {}).get('human_indicators_found', [])
    
    if not text_indicators and not cover_indicators:
        indicators_list = ["No AI indicators detected"]
    else:
        indicators_list = text_indicators + cover_indicators
    
    # Determine styling based on conclusion
    conclusion_lower = ai_conclusion.lower()
    
    if 'human' in conclusion_lower:
        ai_bg = "#e8f5e8"  # Green
        ai_border = "#4caf50"
        ai_icon = "✍️✅"
        ai_title = "HUMAN-GENERATED CONTENT"
        ai_message = "This appears to be authentically human-written"
        ai_marketing_note = "Marketing Impact: This human-written quality is valuable - it helps create authentic emotional connections with readers and can be highlighted in marketing materials."
    elif 'clearly ai' in conclusion_lower or 'ai-generated' in conclusion_lower:
        ai_bg = "#ffebee"  # Red
        ai_border = "#f44336"
        ai_icon = "🤖⚠️"
        ai_title = "AI-GENERATED CONTENT"
        ai_message = "This book shows strong signs of AI generation"
        ai_marketing_note = "Marketing Impact: AI-generated content often struggles to connect with readers because it lacks authentic human voice and emotional depth. Readers can subconsciously detect when writing feels generic or lacks personal experience. Consider revising to inject more unique voice and personal anecdotes."
    elif 'assisted' in conclusion_lower:
        ai_bg = "#fff3e0"  # Orange
        ai_border = "#ff9800"
        ai_icon = "🤖❓"
        ai_title = "POSSIBLE AI ASSISTANCE"
        ai_message = "This book may have used AI assistance"
        ai_marketing_note = "Marketing Impact: If AI was used, ensure you've added enough of your unique voice and personal experience. Books that feel generic struggle to build reader loyalty and word-of-mouth recommendations."
    else:
        ai_bg = "#f5f5f5"  # Grey
        ai_border = "#999999"
        ai_icon = "❓"
        ai_title = "INCONCLUSIVE"
        ai_message = "AI detection analysis could not determine clearly"
        ai_marketing_note = "Marketing Impact: Consider getting a professional editorial review to assess the manuscript's authenticity and marketability."
    
    body = f"""
    <html>
    <head>
        <style>
            .ai-section {{
                background: {ai_bg};
                border-left: 5px solid {ai_border};
                padding: 20px;
                margin: 20px 0 30px 0;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .ai-icon {{
                font-size: 32px;
                margin-right: 15px;
            }}
            .ai-title {{
                font-size: 20px;
                font-weight: bold;
                margin: 0;
                color: #333;
            }}
            .indicator-list {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
            }}
            .marketing-impact {{
                background: rgba(255,255,255,0.7);
                padding: 15px;
                border-radius: 8px;
                border-left: 3px solid {ai_border};
                margin-top: 15px;
            }}
        </style>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0; opacity: 0.9;">by {author_name}</h3>
        </div>
        
        <!-- AI DETECTION SECTION -->
        <div class="ai-section">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{ai_icon}</span>
                <div>
                    <div class="ai-title">{ai_title}</div>
                </div>
            </div>
            
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {ai_message}</p>
            <p style="color: #555;">{ai_explanation}</p>
            
            <!-- Show text indicators -->
            {f'''
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">📝 Text Analysis:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_indicators[:5]])}
                </ul>
                {f'''
                <p style="margin: 10px 0 5px 0; font-weight: bold;">✨ Human Qualities:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_human_indicators[:3]])}
                </ul>
                ''' if text_human_indicators else ''}
            </div>
            ''' if text_indicators or text_human_indicators else ''}
            
            <!-- Show cover indicators -->
            {f'''
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">🎨 Cover Analysis:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_indicators[:3]])}
                </ul>
                {f'''
                <p style="margin: 10px 0 5px 0; font-weight: bold;">✨ Cover Strengths:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_human_indicators[:3]])}
                </ul>
                ''' if cover_human_indicators else ''}
            </div>
            ''' if cover_indicators or cover_human_indicators else ''}
            
            <!-- Show marketing impact -->
            <div class="marketing-impact">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0; color: #333;">{ai_marketing_note}</p>
            </div>
        </div>
        
        <!-- Marketability Score -->
        <div style="text-align: center; margin: 30px 0 20px 0;">
            <div style="font-size: 72px; font-weight: bold; color: #667eea;">{score}</div>
            <div style="font-size: 24px; color: #666;">Marketability Score ({grade})</div>
        </div>
    """
    
    # Book Overview
    body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📖 Book Overview</h2>
            <p><strong>Genres:</strong> {', '.join(book_info.get('genres', ['Unknown']))}</p>
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
    
    # Conditional signup message based on score
    if overall_score < 70:
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
        
        # Also send to editor
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
        .stButton > button {
            width: 100%;
            height: 60px;
            font-size: 20px;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            margin-top: 20px;
        }
        .stTextInput > div > input {
            height: 50px;
            font-size: 16px;
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
        - 🤖 **AI detection analysis** - Find out if your book shows signs of AI generation
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
    if 'ai_detection' not in st.session_state:
        st.session_state.ai_detection = None
    
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
            # Extract text for analysis only
            st.session_state.text = extract_text_for_analysis(manuscript)
    
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
        Your book is 100% secure and will never be used for training or marketing. By using this service we will add you to the free waitlist without obligation.
    </p>
    """, unsafe_allow_html=True)
    
    if manuscript and email:
        if st.button("🔍 GET MY FREE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 60 seconds)"):
                       
                # Use pre-extracted text
                text = st.session_state.text
                
                # Process cover if provided
                cover_analysis = None
                if cover:
                    cover_analysis = analyze_cover(cover)
                    st.session_state.cover_analysis = cover_analysis
                
                # Run AI detection first
                ai_detection = detect_ai_content(text, cover_analysis)
                st.session_state.ai_detection = ai_detection
                
                # Analyze manuscript (FULL analysis)
                analysis = analyze_book_complete(text, cover_analysis, book_title, author_name)
                
                if analysis:
                    st.session_state.analysis_result = analysis
                    
                    # Get book title and author (use provided or detected)
                    book_info = analysis.get('book_info', {})
                    final_title = book_info.get('title', 'Your Book')
                    final_author = book_info.get('author', 'Unknown Author')
                    
                    # Send email with AI detection results
                    email_sent = send_email(email, analysis, cover_analysis, final_title, final_author, ai_detection)
                    
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
    ai_detection = st.session_state.ai_detection
    marketability = analysis.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    overall_grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis.get('book_info', {})
    book_title = book_info.get('title', 'Your Book')
    author_name = book_info.get('author', 'Unknown Author')
    
    # Get AI detection results for display
    ai_overall = ai_detection.get('overall_assessment', {})
    ai_conclusion = ai_overall.get('conclusion', 'Inconclusive')
    
    # Determine AI warning style
    conclusion_lower = ai_conclusion.lower()
    
    if 'human' in conclusion_lower:
        ai_bg_color = "#e8f5e8"
        ai_border = "#4caf50"
        ai_icon = "✍️✅"
        ai_text = "HUMAN-GENERATED CONTENT"
    elif 'clearly ai' in conclusion_lower or 'ai-generated' in conclusion_lower:
        ai_bg_color = "#ffebee"
        ai_border = "#f44336"
        ai_icon = "🤖⚠️"
        ai_text = "AI-GENERATED CONTENT"
    elif 'assisted' in conclusion_lower:
        ai_bg_color = "#fff3e0"
        ai_border = "#ff9800"
        ai_icon = "🤖❓"
        ai_text = "POSSIBLE AI ASSISTANCE"
    else:
        ai_bg_color = "#f5f5f5"
        ai_border = "#999999"
        ai_icon = "❓"
        ai_text = "INCONCLUSIVE"
    
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
    
    # Show AI detection banner
    st.markdown(f"""
    <div style="padding: 15px; background: {ai_bg_color}; border-left: 5px solid {ai_border}; border-radius: 5px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center;">
            <span style="font-size: 24px; margin-right: 10px;">{ai_icon}</span>
            <div>
                <strong>{ai_text}</strong><br>
                <span style="color: #666;">{ai_overall.get('explanation', '')}</span>
            </div>
        </div>
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
    """Full cover analysis - WITH AI DETECTION built in"""
    
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
        
        # Analyze with OpenAI vision - with specific AI detection instructions
        prompt = """Analyze this book cover in detail and determine if it's AI-generated.
        
        Look for these SPECIFIC AI GENERATION INDICATORS:
        1. TEXT: Any text should be examined - AI often generates gibberish, misspelled words, or nonsensical letters
        2. HANDS/FINGERS: Count fingers on any hands shown - AI frequently gets numbers wrong or creates malformed digits
        3. ANATOMY: Check for impossible body parts, extra limbs, or strange proportions
        4. LIGHTING: Look for inconsistent light sources or shadows that don't make physical sense
        5. BLENDING: Check for areas where objects "melt" into each other or have unnatural transitions
        6. SYMMETRY: AI often fails at symmetrical elements like faces, buildings, or patterns
        7. PERSPECTIVE: Check if architectural elements follow proper perspective (parallel lines should converge)
        8. DETAILS: Look for areas that are overly smooth or lack texture compared to the rest of the image
        
        Return JSON with:
        {
            "colors": ["list of dominant colors"],
            "has_figure": true/false,
            "figure_description": "description if any figures present",
            "typography": "description of font style",
            "composition": "how elements are arranged",
            "mood": "emotional feeling",
            "genre_signals": "what genre this suggests",
            "ai_detection": {
                "is_ai_generated": true/false,
                "confidence": 0-100,
                "indicators_found": ["list specific AI red flags found"],
                "explanation": "brief explanation of why it is or isn't AI"
            },
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
        
        result = json.loads(response.choices[0].message.content)
        return result
        
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
        
        # Improved detection: skip lines that look like URLs or empty
        for i, line in enumerate(first_lines):
            if re.match(r'https?://', line) or len(line) < 5:
                continue
            if i == 0:
                detected_title = line
            if 'by' in line.lower() and len(line) < 100:
                detected_author = re.sub(r'(?i)by', '', line).strip()
                break
        # Fallback if no 'by'
        if detected_author == "Unknown Author" and len(first_lines) > 1:
            detected_author = first_lines[1] if len(first_lines[1]) < 50 else "Unknown Author"
    
    # GENRE CLASSIFICATION RULES
    genre_rules = """
    GENRE CLASSIFICATION RULES - READ CAREFULLY:
    - If the book is a personal story about the author's own life experiences → use "Memoir"
    - "Non-Fiction" is ONLY for encyclopedias, textbooks, how-to books, informational guides
    - DO NOT use "Non-Fiction" for memoirs, biographies, or autobiographies
    - You can select MULTIPLE genres that fit (e.g., a memoir could also be LGBTQ+ Fiction)
    - List them in order of relevance
    """
    
    # ALLOWED GENRES LIST WITH DESCRIPTIONS
    allowed_genres_text = """
    ALLOWED GENRES (use ONLY these for genre and subgenres):
    - Romance: Books centered on romantic relationships, love stories, and emotional connections between characters, often with happy endings.
    - Fantasy: Stories involving magic, mythical creatures, imaginary worlds, quests, or supernatural elements.
    - Romantasy: A hybrid of romance and fantasy, blending deep romantic relationships with magical worlds, epic quests, and supernatural elements.
    - Science Fiction: Speculative stories exploring futuristic technology, space exploration, alternate realities, dystopias, or scientific concepts.
    - Mystery: Narratives built around solving a puzzle, crime, or secret, usually featuring investigation and revelation.
    - Thriller: Fast-paced, suspenseful stories designed to create tension, danger, and excitement, often with high stakes.
    - Horror: Stories intended to frighten, disturb, or unsettle readers through fear, the supernatural, or psychological terror.
    - Young Adult: Fiction aimed at teenagers (roughly ages 12–18), typically featuring coming-of-age themes, identity, and first experiences.
    - Historical Fiction: Stories set in the past that blend real historical events or settings with fictional characters and plots.
    - Contemporary Fiction: Modern-day stories focusing on realistic characters, relationships, and everyday life issues.
    - Literary Fiction: Character-driven, introspective stories that emphasize style, language, themes, and emotional depth over plot.
    - Children's: Books written for young children, usually with simple language, illustrations, and moral lessons.
    - Middle Grade: Stories for ages 8–12, often featuring adventure, friendship, family, school life, or light fantasy.
    - Non-Fiction: Factual writing covering real events, people, ideas, or information. (ONLY for informational books, NOT personal memoirs)
    - Memoir: Personal, true accounts of the author's own experiences, usually focused on specific themes or periods of life.
    - Biography: A detailed account of a real person's life, written by someone else, based on research and sources.
    - Autobiography: A full, chronological account of the author's own entire life, written by the person themselves.
    - Self-Help: Practical books offering advice, strategies, or guidance for personal improvement, success, health, or happiness.
    - LGBTQ+ Fiction: Stories that center queer characters, identities, relationships, and experiences.
    - Paranormal: Fiction involving ghosts, vampires, werewolves, psychics, or other supernatural phenomena.
    - Graphic Novels: Long-form stories told through sequential art and text, similar in length and complexity to novels.
    - Comics: Shorter or serialized stories told through panels and illustrations, often in series or anthologies.
    - Classics: Timeless, influential works of literature that have enduring cultural or literary significance.
    - Erotica: Fiction that focuses explicitly on sexual desire, arousal, and intimate encounters.
    
    IMPORTANT: Genre and subgenres MUST be chosen ONLY from this list. DO NOT invent genres.
    You can select MULTIPLE genres that fit the book.
    """
    
    prompt = f"""
    You are a professional literary analyst. Analyze THIS SPECIFIC BOOK based SOLELY on the manuscript excerpts provided below.
    
    BOOK TITLE (detected from manuscript): {detected_title}
    AUTHOR (detected from manuscript): {detected_author}
    
    {cover_text}
    
    {genre_rules}
    
    {allowed_genres_text}
    
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
            "genres": ["primary genre from approved list", "secondary genre if applicable", "another if applicable"],
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
        
        # Ensure title and author are set
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
