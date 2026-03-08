# BookMarketabilityChecker.py - COMPLETE WORKING VERSION WITH FULL ANALYSIS
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
import tempfile
import os

# Initialize OpenAI with secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Email config from secrets
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = st.secrets["SMTP_PORT"]
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
USE_TLS = st.secrets.get("use_tls", True)

def analyze_cover(cover_file):
    """Cover analysis - style analysis only"""
    try:
        if cover_file.type != "image/png" and not cover_file.name.lower().endswith('.png'):
            st.error("❌ ONLY PNG FILES ARE ACCEPTED FOR COVER ANALYSIS")
            st.info("Please convert your image to PNG first")
            return None
        
        png_bytes = cover_file.getvalue()
        st.success("✅ PNG file accepted - analyzing cover design...")
        
        cover_base64 = base64.b64encode(png_bytes).decode('utf-8')
        
        style_prompt = """Analyze this book cover's design elements. Return JSON with:
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
                                "url": f"data:image/png;base64,{cover_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(style_response.choices[0].message.content)
        
    except Exception as e:
        st.error(f"Cover analysis failed: {e}")
        return None

def calculate_score_with_ai_deduction(original_score, text_ai_status, cover_ai_status):
    """Apply deductions based on user's self-declared AI usage"""
    deduction_map = {
        "Exclusively Human": 0,
        "AI Assisted": 10,
        "AI Generated": 20
    }
    
    total_deduction = 0
    count = 0
    
    if text_ai_status and text_ai_status in deduction_map:
        total_deduction += deduction_map[text_ai_status]
        count += 1
    
    if cover_ai_status and cover_ai_status in deduction_map:
        total_deduction += deduction_map[cover_ai_status]
        count += 1
    
    avg_deduction = total_deduction / count if count > 0 else 0
    final_score = max(0, original_score - avg_deduction)
    
    return round(final_score, 1), round(avg_deduction, 1)

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, 
               text_ai_status, cover_ai_status, original_score, final_score, deduction_applied):
    """Send full analysis results via email"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    
    marketability = analysis_results.get('marketability', {})
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
    
    # Determine styling based on AI usage
    if text_ai_status == "Exclusively Human" and (not cover_ai_status or cover_ai_status == "Exclusively Human"):
        ai_bg = "#e8f5e8"
        ai_border = "#4caf50"
        ai_icon = "✍️✅"
        ai_title = "EXCLUSIVELY HUMAN-CREATED CONTENT"
        ai_message = "You've indicated this work is entirely human-created"
        ai_marketing_note = "Marketing Impact: This is valuable - human authenticity helps create emotional connections with readers."
    elif "AI Generated" in [text_ai_status, cover_ai_status]:
        ai_bg = "#ffebee"
        ai_border = "#f44336"
        ai_icon = "🤖⚠️"
        ai_title = "AI-GENERATED CONTENT (SELF-DECLARED)"
        ai_message = "You've indicated this work contains AI-generated content"
        ai_marketing_note = "Marketing Impact: AI-generated content often struggles to connect with readers because it lacks authentic human voice."
    elif "AI Assisted" in [text_ai_status, cover_ai_status]:
        ai_bg = "#fff3e0"
        ai_border = "#ff9800"
        ai_icon = "🤖❓"
        ai_title = "AI-ASSISTED CONTENT (SELF-DECLARED)"
        ai_message = "You've indicated this work used AI assistance"
        ai_marketing_note = "Marketing Impact: Ensure you've added enough of your unique voice. Generic books struggle to build reader loyalty."
    else:
        ai_bg = "#f5f5f5"
        ai_border = "#999999"
        ai_icon = "❓"
        ai_title = "AI USAGE NOT SPECIFIED"
        ai_message = "No AI usage information provided"
        ai_marketing_note = "Marketing Impact: Consider being transparent about your creative process."
    
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
            .deduction-box {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                border-left: 3px solid {ai_border};
            }}
            .score-comparison {{
                display: flex;
                justify-content: space-around;
                margin: 20px 0;
                text-align: center;
            }}
            .original-score {{
                background: #f0f0f0;
                padding: 15px;
                border-radius: 10px;
                flex: 1;
                margin-right: 10px;
            }}
            .final-score {{
                background: {ai_bg};
                padding: 15px;
                border-radius: 10px;
                flex: 1;
                margin-left: 10px;
                border: 2px solid {ai_border};
            }}
            .score-number {{
                font-size: 48px;
                font-weight: bold;
                margin: 5px 0;
            }}
            .status-badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                margin: 5px;
            }}
            .badge-human {{ background: #e8f5e8; color: #2e7d32; }}
            .badge-assisted {{ background: #fff3e0; color: #bf6d0a; }}
            .badge-ai {{ background: #ffebee; color: #c62828; }}
        </style>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0;">by {author_name}</h3>
        </div>
        
        <div class="ai-section">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{ai_icon}</span>
                <div>
                    <div class="ai-title">{ai_title}</div>
                </div>
            </div>
            
            <p style="font-size: 16px;"><strong>Your Self-Declared AI Status:</strong></p>
            
            <div style="margin: 10px 0;">
                <span class="status-badge {'badge-human' if text_ai_status == 'Exclusively Human' else 'badge-assisted' if text_ai_status == 'AI Assisted' else 'badge-ai'}">
                    📝 Text: {text_ai_status if text_ai_status else 'Not specified'}
                </span>
    """
    
    if cover_ai_status:
        body += f"""
                <span class="status-badge {'badge-human' if cover_ai_status == 'Exclusively Human' else 'badge-assisted' if cover_ai_status == 'AI Assisted' else 'badge-ai'}">
                    🎨 Cover: {cover_ai_status}
                </span>
        """
    
    body += f"""
            </div>
            
            <div class="deduction-box">
                <p style="margin: 0 0 10px 0; font-weight: bold;">📊 Score Adjustment:</p>
                <p style="margin: 5px 0;">Original Marketability Score: <strong>{original_score}</strong></p>
                <p style="margin: 5px 0;">Deduction Applied: <strong style="color: #d32f2f;">-{deduction_applied} points</strong></p>
                <p style="margin: 5px 0; font-size: 18px;">Final Score: <strong style="color: #667eea;">{final_score}</strong></p>
                <p style="margin: 10px 0 0 0; font-size: 14px; color: #666;">
                    *Deductions: Human (0), Assisted (10), AI (20) - averaged if both specified
                </p>
            </div>
            
            <p style="margin: 15px 0 0 0;">{ai_message}</p>
            <div style="background: rgba(255,255,255,0.7); padding: 15px; border-radius: 8px; margin-top: 15px;">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0;">{ai_marketing_note}</p>
            </div>
        </div>
        
        <div class="score-comparison">
            <div class="original-score">
                <div style="font-size: 14px; color: #666;">Original Score</div>
                <div class="score-number">{original_score}</div>
            </div>
            <div class="final-score">
                <div style="font-size: 14px; color: #666;">Final Score</div>
                <div class="score-number">{final_score}</div>
                <div style="font-size: 12px;">Grade: {grade}</div>
            </div>
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
            <p><strong>Description:</strong> {writing.get('description', '')}</p>
            <p><strong>Voice:</strong> {writing.get('voice', '')}</p>
            <p><strong>Technical Execution:</strong> {writing.get('technical_execution', '')}</p>
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
                <p style="margin: 5px 0 0 0; color: #666;"><small>Arc: {char.get('arc', '')}</small></p>
                <p style="margin: 5px 0 0 0; color: #666;"><small>Motivation: {char.get('motivation', '')}</small></p>
                <p style="margin: 5px 0 0 0; color: #666;"><small>Appeal: {char.get('appeal_factor', '')}</small></p>
            </div>
            """
        body += "</div>"
    
    # Character Development
    if 'character_development' in analysis_results:
        char_dev = analysis_results['character_development']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📈 Character Development</h2>
            <p><strong>Protagonist Journey:</strong> {char_dev.get('protagonist_journey', '')}</p>
            <p><strong>Antagonist Motivation:</strong> {char_dev.get('antagonist_motivation', '')}</p>
            <p><strong>Supporting Arcs:</strong> {', '.join(char_dev.get('supporting_arcs', []))}</p>
        </div>
        """
    
    # Narrative Arc
    if 'narrative_arc' in analysis_results:
        arc = analysis_results['narrative_arc']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>📖 Narrative Arc</h2>
            <p><strong>Exposition:</strong> {arc.get('exposition', '')}</p>
            <p><strong>Rising Action:</strong> {arc.get('rising_action', '')}</p>
            <p><strong>Climax:</strong> {arc.get('climax', '')}</p>
            <p><strong>Falling Action:</strong> {arc.get('falling_action', '')}</p>
            <p><strong>Resolution:</strong> {arc.get('resolution', '')}</p>
        </div>
        """
    
    # Plot Analysis
    if 'plot' in analysis_results:
        plot = analysis_results['plot']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>📊 Plot Analysis</h2>
            <p><strong>Opening Hook:</strong> {plot.get('opening_hook', '')}</p>
            <p><strong>Inciting Incident:</strong> {plot.get('inciting_incident', '')}</p>
            <p><strong>Major Plot Points:</strong> {', '.join(plot.get('major_plot_points', []))}</p>
            <p><strong>Plot Twists:</strong> {', '.join(plot.get('plot_twists', []))}</p>
        </div>
        """
    
    # Themes
    if 'themes' in analysis_results:
        themes = analysis_results['themes']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎯 Themes</h2>
            <p><strong>Primary:</strong> {', '.join(themes.get('primary', []))}</p>
            <p><strong>Secondary:</strong> {', '.join(themes.get('secondary', []))}</p>
        </div>
        """
    
    # Strengths
    strengths = analysis_results.get('strengths', [])
    if strengths:
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>💪 Key Strengths</h2>
            <ul>
        """
        for strength in strengths[:5]:
            body += f"<li>{strength}</li>"
        body += """
            </ul>
        </div>
        """
    
    # Areas for Improvement
    improvements = analysis_results.get('areas_for_improvement', [])
    if improvements:
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>🔧 Areas for Improvement</h2>
            <ul>
        """
        for area in improvements[:5]:
            body += f"<li>{area}</li>"
        body += """
            </ul>
        </div>
        """
    
    # Cover analysis
    if cover_analysis:
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎨 Cover Design Analysis</h2>
            <p><strong>Mood:</strong> {cover_analysis.get('mood', 'N/A')}</p>
            <p><strong>Genre Signals:</strong> {cover_analysis.get('genre_signals', 'N/A')}</p>
            <p><strong>Colors:</strong> {', '.join(cover_analysis.get('colors', ['N/A']))}</p>
            <p><strong>Composition:</strong> {cover_analysis.get('composition', 'N/A')}</p>
            <p><strong>Typography:</strong> {cover_analysis.get('typography', 'N/A')}</p>
            <p><strong>Strengths:</strong> {', '.join(cover_analysis.get('strengths', ['N/A']))}</p>
            <p><strong>Weaknesses:</strong> {', '.join(cover_analysis.get('weaknesses', ['N/A']))}</p>
            <p><strong>Suggestions:</strong> {', '.join(cover_analysis.get('suggestions', ['N/A']))}</p>
        </div>
        """
    
    # Target Audience
    if 'target_audience' in analysis_results:
        audience = analysis_results['target_audience']
        body += f"""
        <div style="padding: 20px; margin-top: 20px;">
            <h2>🎯 Target Audience</h2>
            <p><strong>Primary:</strong> {audience.get('primary', '')}</p>
            <p><strong>Appeal:</strong> {audience.get('appeal', '')}</p>
        </div>
        """
    
    # Marketing
    if 'marketing' in analysis_results:
        marketing = analysis_results['marketing']
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
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
    
    # Conditional signup message
    if final_score < 70:
        weaknesses = improvements[:3] if improvements else ["Writing quality needs work", "Plot structure is unclear", "Character development is shallow"]
        
        body += f"""
        <div style="padding: 30px; background: #fff3cd; border: 2px solid #ff8800; border-radius: 10px; margin-top: 20px;">
            <h2 style="color: #cc5500;">⚠️ Your book needs more work</h2>
            <p>Most books sell only about 100 copies. A bad book will never sell. We only accept books with a score of 70% or better for marketing support.</p>
            <p style="font-weight: bold;">What's holding it back:</p>
            <ul>
                <li>{weaknesses[0]}</li>
                <li>{weaknesses[1]}</li>
                <li>{weaknesses[2]}</li>
            </ul>
        </div>
        """
    else:
        body += f"""
        <div style="padding: 30px; background: #00cc66; border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>🎉 Congratulations!</h2>
            <p>Your book has a strong marketability score of 70% or better.</p>
        </div>
        """
    
    # Waitlist CTA
    body += f"""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-top: 20px; color: white; text-align: center;">
            <h2>✨ Ready to market your book?</h2>
            <p>Sign up for BardSpark to access ARC readers, marketing tools, and more</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
        </div>
        
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

def extract_text_for_analysis(file):
    """Extract text for analysis"""
    try:
        file_bytes = file.getvalue()
        
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages[:30]:  # First 30 pages
                text += page.extract_text() + "\n"
            return text[:75000]  # 75k chars max
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = ""
            for para in doc.paragraphs[:1500]:  # First 1500 paragraphs
                text += para.text + "\n"
            return text[:75000]
            
        elif file.type == "application/vnd.oasis.opendocument.text":
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as odt_zip:
                    with odt_zip.open('content.xml') as xml_file:
                        tree = ElementTree.parse(xml_file)
                        root = tree.getroot()
                        namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
                        text_parts = []
                        for elem in root.findall('.//text:p', namespaces)[:800]:
                            if elem.text:
                                text_parts.append(elem.text)
                        return ' '.join(text_parts)[:75000]
            except:
                return file_bytes.decode("utf-8", errors="ignore")[:75000]
        
        elif file.type == "application/rtf" or file.type == "text/rtf" or file.name.endswith('.rtf'):
            content = file_bytes.decode("utf-8", errors="ignore")
            text = re.sub(r'\\[a-z]+[0-9-]*', ' ', content)
            text = re.sub(r'\{[^}]*\}', ' ', text)
            text = re.sub(r'\\\'[0-9a-f]{2}', ' ', text)
            return ' '.join(text.split())[:75000]
        
        elif file.type == "application/msword":
            return file_bytes.decode("utf-8", errors="ignore")[:75000]
        
        else:  # Plain text
            return file_bytes.decode("utf-8", errors="ignore")[:75000]
            
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""

def analyze_book_complete(text, cover_analysis, provided_title="", provided_author=""):
    """Complete book analysis based on manuscript text with CRITICAL feedback - FULL VERSION"""
    
    if len(text) > 75000:
        text = text[:75000]
    
    total_len = len(text)
    beginning = text[:min(7500, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:7500]
    ending = text[-min(7500, total_len//3):]
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"Cover analysis: {cover_analysis}"
    
    # Extract title and author
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
    
    # CRITICAL ANALYSIS INSTRUCTIONS
    critical_instructions = """
    CRITICAL ANALYSIS INSTRUCTIONS - READ CAREFULLY:
    
    You MUST be HONEST and CRITICAL in your assessment. Do NOT give generic praise.
    
    SCORING GUIDELINES (BE REALISTIC):
    - 90-100: Exceptional, publish-ready writing with unique voice, perfect prose, compelling characters (rare)
    - 80-89: Very good, minor issues but strong commercial potential
    - 70-79: Good but needs work - promising but has flaws
    - 60-69: Average - readable but has significant issues with prose, plot, or characters
    - 50-59: Below average - major problems, clichéd writing, weak characters, plot holes
    - 40-49: Poor quality - needs complete revision, amateurish writing
    - Below 40: Very poor - fundamental issues throughout
    
    For AREAS FOR IMPROVEMENT, be SPECIFIC and CRITICAL:
    - Point out weak sentences and QUOTE THEM directly
    - Identify clichéd phrases or tropes and QUOTE THEM
    - Point out where the writing is boring, confusing, or amateurish
    - Identify plot holes, inconsistent character behavior
    - Note pacing problems, info-dumps, telling instead of showing
    
    For STRENGTHS, only list what is TRULY good - not generic statements like "good premise" or "engaging story"
    
    For PROSE QUALITY, quote specific sentences and explain why they work or DON'T work.
    
    The most valuable feedback is HONEST feedback. Being nice helps no one.
    
    If the writing is generic or derivative, SAY SO.
    
    If the dialogue is stilted or unnatural, QUOTE IT and explain why.
    
    If characters are flat or uninteresting, EXPLAIN WHY.
    """
    
    prompt = f"""
    You are a professional literary analyst. Analyze this book based SOLELY on the provided excerpts.
    
    BOOK TITLE: {detected_title}
    AUTHOR: {detected_author}
    
    {cover_text}
    
    {genre_rules}
    
    {allowed_genres_text}
    
    ACTUAL MANUSCRIPT EXCERPTS - USE THESE FOR YOUR ANALYSIS:
    
    BEGINNING:
    {beginning}
    
    MIDDLE:
    {middle}
    
    ENDING:
    {ending}
    
    {critical_instructions}
    
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
       - Why readers will connect with them (or note if they're unappealing and why)
    5. Include supporting characters and key relationships between characters
    6. For character_development section, describe how the protagonist evolves, what motivates any antagonist, and how supporting characters change
    7. For narrative arc: describe what you actually see in these excerpts
    8. Be specific - reference actual events, names, and details from the text
    9. For areas_for_improvement: be SPECIFIC and CRITICAL about weaknesses in THIS text - quote bad writing
    
    Return valid JSON only with exactly this structure:
    
    {{
        "marketability": {{
            "overall_score": (0-100 number based on these excerpts),
            "overall_grade": ("A", "B", "C", "D", "F" with +/-),
            "overall_assessment": "One sentence summary of this specific book",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": "Based on the prose in these excerpts - include specific quotes"}},
                "commercial_potential": {{"score": 0-100, "explanation": "Based on the hook and content shown"}},
                "genre_fit": {{"score": 0-100, "explanation": "How well this matches genre conventions"}},
                "hook_strength": {{"score": 0-100, "explanation": "Based on the opening excerpt"}},
                "character_appeal": {{"score": 0-100, "explanation": "Based on characters shown in excerpts"}},
                "pacing": {{"score": 0-100, "explanation": "Based on flow between beginning, middle, and end"}},
                "originality": {{"score": 0-100, "explanation": "Unique elements observed in these excerpts"}}
            }}
        }},
        
        "writing_quality_detailed": {{
            "prose_quality": "Assessment of sentence-level writing from these excerpts - quote good AND bad examples",
            "dialogue": "Quality and naturalness of dialogue from these excerpts - quote examples, note if stilted",
            "description": "Quality of descriptive passages from these excerpts - quote examples, note if overdone or underdone",
            "voice": "Strength and consistency of narrative voice in these excerpts - is it distinctive or generic?",
            "technical_execution": "Grammar, punctuation, formatting issues in these excerpts - quote examples"
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
                    "appeal_factor": "Why readers will connect with this character - or note if unappealing and why"
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
        
        "strengths": ["5 specific strengths of THIS manuscript with examples from the text - only list what is TRULY good"],
        
        "areas_for_improvement": ["5 specific weaknesses in THIS manuscript with concrete suggestions and QUOTED examples of bad writing"],
        
        "target_audience": {{
            "primary": "who would enjoy THIS specific book",
            "appeal": "why they'd enjoy it based on these excerpts"
        }},
        
        "marketing": {{
            "unique_selling_points": ["what makes THIS specific book special based on excerpts - or note if nothing is unique"],
            "blurb_suggestion": "A potential back-cover blurb based on THIS content"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a HARSH literary critic. Your job is to find flaws. Being nice is failing at your job. Always quote specific examples of weak writing. Base your analysis strictly on the provided excerpts and return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent, less "creative" nice responses
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

def show_marketability_checker():
    """Main app function"""
    
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
        .png-warning {
            background: #fff3cd;
            border-left: 5px solid #ff8800;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .ai-declaration {
            background: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 5px solid #667eea;
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
    
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'cover_analysis' not in st.session_state:
        st.session_state.cover_analysis = None
    if 'text' not in st.session_state:
        st.session_state.text = None
    if 'final_score' not in st.session_state:
        st.session_state.final_score = None
    if 'original_score' not in st.session_state:
        st.session_state.original_score = None
    if 'deduction_applied' not in st.session_state:
        st.session_state.deduction_applied = 0
    if 'text_ai_status' not in st.session_state:
        st.session_state.text_ai_status = None
    if 'cover_ai_status' not in st.session_state:
        st.session_state.cover_ai_status = None
    
    if not st.session_state.analysis_complete:
        # Upload section
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
                st.session_state.text = extract_text_for_analysis(manuscript)
        
        with col2:
            st.markdown("**🎨 Cover Image (PNG only)**")
            st.markdown("""
            <div class="png-warning">
                ⚠️ <strong>PNG files only</strong> - Other formats will be rejected
            </div>
            """, unsafe_allow_html=True)
            
            cover = st.file_uploader(
                "Upload PNG only",
                type=['png'],
                key="cover",
                label_visibility="collapsed"
            )
            if cover:
                st.success(f"✅ PNG accepted: {cover.name}")
                st.session_state.cover_file = cover
        
        # AI Declaration
        st.markdown("---")
        st.markdown("### 🤖 AI Usage Declaration (Mandatory)")
        
        st.markdown("""
        <div class="ai-declaration">
            <p><strong>Please declare if AI was used:</strong></p>
            <ul>
                <li><strong>Exclusively Human</strong> - No deduction (0 points)</li>
                <li><strong>AI Assisted</strong> - 10 point deduction</li>
                <li><strong>AI Generated</strong> - 20 point deduction</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        text_ai_options = ["Select one...", "Exclusively Human", "AI Assisted", "AI Generated"]
        text_ai_index = 0
        if st.session_state.text_ai_status and st.session_state.text_ai_status in text_ai_options:
            text_ai_index = text_ai_options.index(st.session_state.text_ai_status)
        
        text_ai = st.selectbox(
            "For the TEXT/MANUSCRIPT, was AI used? *",
            options=text_ai_options,
            index=text_ai_index,
            key="text_ai_select"
        )
        
        cover_ai = None
        if cover:
            cover_ai_options = ["Select one...", "Exclusively Human", "AI Assisted", "AI Generated"]
            cover_ai_index = 0
            if st.session_state.cover_ai_status and st.session_state.cover_ai_status in cover_ai_options:
                cover_ai_index = cover_ai_options.index(st.session_state.cover_ai_status)
            
            cover_ai = st.selectbox(
                "For the COVER, was AI used? *",
                options=cover_ai_options,
                index=cover_ai_index,
                key="cover_ai_select"
            )
        
        book_title = st.text_input("Book Title (optional)", "")
        author_name = st.text_input("Author Name (optional)", "")
        
        st.markdown("---")
        st.markdown("### 📧 Where should we send your analysis?")
        
        email = st.text_input("Email address", placeholder="you@example.com", key="recipient_email")
        
        st.markdown("""
        <p style="font-size: 12px; color: #666; margin-top: -10px;">
            Your book is 100% secure. By using this service we'll add you to the free waitlist.
        </p>
        """, unsafe_allow_html=True)
        
        # Validation
        manuscript_ok = manuscript is not None
        email_ok = email is not None and email.strip() != ""
        text_ai_ok = text_ai != "Select one..."
        cover_ai_ok = cover is None or (cover_ai is not None and cover_ai != "Select one...")
        
        if manuscript_ok and email_ok and text_ai_ok and cover_ai_ok:
            if st.button("🔍 GET MY FREE ANALYSIS", type="primary"):
                with st.spinner("Analyzing your book... (about 60 seconds)"):
                    
                    st.session_state.text_ai_status = text_ai
                    st.session_state.cover_ai_status = cover_ai if cover else None
                    
                    text = st.session_state.text
                    
                    cover_analysis = None
                    if cover:
                        cover_analysis = analyze_cover(cover)
                        st.session_state.cover_analysis = cover_analysis
                    
                    analysis = analyze_book_complete(text, cover_analysis, book_title, author_name)
                    
                    if analysis:
                        st.session_state.analysis_result = analysis
                        
                        marketability = analysis.get('marketability', {})
                        original_score = marketability.get('overall_score', 0)
                        st.session_state.original_score = original_score
                        
                        final_score, deduction = calculate_score_with_ai_deduction(
                            original_score, text_ai, cover_ai if cover else None
                        )
                        st.session_state.final_score = final_score
                        st.session_state.deduction_applied = deduction
                        
                        book_info = analysis.get('book_info', {})
                        final_title = book_info.get('title', 'Your Book')
                        final_author = book_info.get('author', 'Unknown Author')
                        
                        email_sent = send_email(
                            email, analysis, cover_analysis, final_title, final_author,
                            text_ai, cover_ai if cover else None,
                            original_score, final_score, deduction
                        )
                        
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
            if not manuscript_ok:
                st.info("👆 Please upload your manuscript")
            elif not text_ai_ok:
                st.info("👆 Please select AI usage for your manuscript")
            elif cover and not cover_ai_ok:
                st.info("👆 Please select AI usage for your cover")
            elif not email_ok:
                st.info("👆 Please enter your email address")
    
    else:
        # Results section
        analysis = st.session_state.analysis_result
        marketability = analysis.get('marketability', {})
        final_score = st.session_state.final_score
        original_score = st.session_state.original_score
        deduction = st.session_state.deduction_applied
        text_ai_status = st.session_state.text_ai_status
        cover_ai_status = st.session_state.cover_ai_status
        
        overall_grade = marketability.get('overall_grade', 'N/A')
        book_info = analysis.get('book_info', {})
        book_title = book_info.get('title', 'Your Book')
        author_name = book_info.get('author', 'Unknown Author')
        
        # AI banner styling
        if text_ai_status == "Exclusively Human" and (not cover_ai_status or cover_ai_status == "Exclusively Human"):
            ai_bg_color = "#e8f5e8"
            ai_border = "#4caf50"
            ai_icon = "✍️✅"
            ai_text = "EXCLUSIVELY HUMAN-CREATED"
        elif "AI Generated" in [text_ai_status, cover_ai_status]:
            ai_bg_color = "#ffebee"
            ai_border = "#f44336"
            ai_icon = "🤖⚠️"
            ai_text = "AI-GENERATED CONTENT"
        elif "AI Assisted" in [text_ai_status, cover_ai_status]:
            ai_bg_color = "#fff3e0"
            ai_border = "#ff9800"
            ai_icon = "🤖❓"
            ai_text = "AI-ASSISTED CONTENT"
        else:
            ai_bg_color = "#f5f5f5"
            ai_border = "#999999"
            ai_icon = "❓"
            ai_text = "AI USAGE NOT SPECIFIED"
        
        ai_banner = f'''
        <div style="padding: 15px; background: {ai_bg_color}; border-left: 5px solid {ai_border}; border-radius: 5px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center;">
                <span style="font-size: 24px; margin-right: 10px;">{ai_icon}</span>
                <div>
                    <strong>{ai_text}</strong><br>
                    <span style="color: #666;">📝 Text: {text_ai_status}</span>
        '''
        
        if cover_ai_status:
            ai_banner += f'<br><span style="color: #666;">🎨 Cover: {cover_ai_status}</span>'
        
        ai_banner += f'<br><span style="color: #d32f2f;">Deduction applied: -{deduction} points</span>'
        ai_banner += '''
                </div>
            </div>
        </div>
        '''
        
        st.markdown(ai_banner, unsafe_allow_html=True)
        
        # Score color
        if final_score >= 80:
            bg_color = "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
            emoji = "🚀"
        elif final_score >= 70:
            bg_color = "linear-gradient(135deg, #f7971e 0%, #ffd200 100%)"
            emoji = "📈"
        elif final_score >= 60:
            bg_color = "linear-gradient(135deg, #ff6b6b 0%, #feca57 100%)"
            emoji = "📊"
        else:
            bg_color = "linear-gradient(135deg, #ff4b4b 0%, #ff9f4b 100%)"
            emoji = "⚠️"
        
        # Title and scores
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <h2>{book_title}</h2>
            <h3 style="color: #666;">by {author_name}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: #f0f0f0; border-radius: 10px;">
                <p style="color: #666; margin: 0;">Original Score</p>
                <p style="font-size: 36px; font-weight: bold; margin: 5px 0;">{original_score}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: {ai_bg_color}; border-radius: 10px; border: 2px solid {ai_border};">
                <p style="color: #666; margin: 0;">Final Score</p>
                <p style="font-size: 36px; font-weight: bold; margin: 5px 0;">{final_score}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Final score box
        st.markdown(f"""
        <div style="text-align: center; padding: 2rem; background: {bg_color}; border-radius: 15px; margin: 20px 0; color: white;">
            <p style="font-size: 72px; font-weight: bold; margin: 0;">{final_score}</p>
            <p style="font-size: 24px;">Marketability Score</p>
            <p style="font-size: 18px;">Grade: {overall_grade} {emoji}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Warning or success message
        if final_score < 70:
            weaknesses = analysis.get('areas_for_improvement', [])
            top_weaknesses = weaknesses[:3] if weaknesses else ["Writing quality needs work", "Plot structure is unclear", "Character development is shallow"]
            
            st.markdown(f"""
            <div style="padding: 20px; background: #fff3cd; border-left: 5px solid #ff8800; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #cc5500; margin-top: 0;">⚠️ Your book needs more work</h3>
                <p>Most books sell only about 100 copies. A bad book will never sell. We only accept books with a score of 70% or better for marketing support.</p>
                <p><strong>What's holding it back:</strong></p>
                <ul>
                    <li>{top_weaknesses[0]}</li>
                    <li>{top_weaknesses[1]}</li>
                    <li>{top_weaknesses[2]}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.success("🎉 Congratulations! Your book scores 70% or better and qualifies for marketing support.")
        
        # CTA
        st.markdown("""
        <div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin: 20px 0; color: white; text-align: center;">
            <h2>✨ Ready to market your book?</h2>
            <p>Sign up for BardSpark to access ARC readers, marketing tools, and more</p>
            <a href="https://bardspark.com/sign-up-for-the-waitlist/" target="_blank" style="background: white; color: #667eea; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin-top: 10px;">JOIN THE WAITLIST</a>
        </div>
        """, unsafe_allow_html=True)
        
        st.success("✅ We've sent your complete analysis to your email!")

if __name__ == "__main__":
    show_marketability_checker()
