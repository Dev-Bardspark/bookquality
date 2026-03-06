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
import zipfile
from xml.etree import ElementTree
import fitz  # PyMuPDF for PDF cover extraction
import tempfile
import os

# Import your PERFECT PNG-only cover detector
import ai_cover_detector_gpt4o_mini_png_only as ai_cover

# Initialize OpenAI with secrets
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Email config from secrets
SMTP_SERVER = st.secrets["SMTP_SERVER"]
SMTP_PORT = st.secrets["SMTP_PORT"]
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
USE_TLS = st.secrets.get("use_tls", True)

def analyze_cover(cover_file):
    """Cover analysis using your PERFECT PNG-only detector"""
    try:
        # Check if it's a PNG
        if cover_file.type != "image/png" and not cover_file.name.lower().endswith('.png'):
            st.error("❌ ONLY PNG FILES ARE ACCEPTED")
            st.info("Please convert your image to PNG first")
            return None
        
        # Get PNG bytes
        png_bytes = cover_file.getvalue()
        st.success("✅ PNG file accepted")
        
        # Detect AI using your function
        ai_detection_json = ai_cover.detect_ai_cover(png_bytes)
        ai_detection_result = json.loads(ai_detection_json)
        
        # Style analysis
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
        
        style_result = json.loads(style_response.choices[0].message.content)
        
        # Combine
        result = {
            **style_result,
            "ai_detection": {
                "is_ai_generated": ai_detection_result.get("verdict") == "likely_ai",
                "verdict": ai_detection_result.get("verdict", "inconclusive"),
                "confidence": ai_detection_result.get("confidence", 0),
                "indicators_found": ai_detection_result.get("key_indicators", []),
                "explanation": ai_detection_result.get("explanation", "")
            }
        }
        
        return result
        
    except Exception as e:
        st.error(f"Cover analysis failed: {e}")
        return None

def detect_ai_content(text, cover_analysis=None):
    """
    ORIGINAL WORKING AI DETECTOR - identifies AI but doesn't score
    """
    # Extract cover AI info if available
    cover_indicators = []
    cover_human = []
    cover_ai_summary = ""
    
    if cover_analysis and 'ai_detection' in cover_analysis:
        ai_detect = cover_analysis['ai_detection']
        cover_indicators = ai_detect.get('indicators_found', [])
        if ai_detect.get('is_ai_generated', False):
            cover_ai_summary = f"Cover appears AI-generated: {ai_detect.get('explanation', '')}"
        else:
            cover_human = ["Thoughtful composition", "Consistent lighting", "Professional design"]
            cover_ai_summary = f"Cover appears human-designed: {ai_detect.get('explanation', '')}"
    
    prompt = f"""
    Analyze this book manuscript excerpt for signs of AI generation.
    
    MANUSCRIPT EXCERPT:
    {text[:10000]}  # First 10,000 chars for analysis
    
    COVER ANALYSIS SUMMARY:
    {cover_ai_summary}
    
    Look for these AI indicators in the TEXT:
    - Overuse of common AI transition phrases ("Furthermore", "Moreover", "In conclusion", "It is important to note")
    - Repetitive sentence structures
    - Generic descriptions lacking specific sensory details
    - Predictable dialogue patterns
    - Lack of authentic voice or personality
    - Hallucinated facts or inconsistencies
    - Too "perfect" grammar with no stylistic quirks
    
    Return JSON with:
    {{
        "text_analysis": {{
            "indicators_found": ["list of specific AI signs in the text - if none, leave empty"],
            "human_indicators_found": ["list of human-written signs - e.g., 'unique voice', 'emotional depth', 'specific sensory details']
        }},
        "cover_analysis": {{
            "indicators_found": {json.dumps(cover_indicators)},
            "human_indicators_found": {json.dumps(cover_human)}
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
                {"role": "system", "content": "You are an AI detection expert. Analyze the text and return your conclusion using ONLY one of these exact phrases: 'Likely human-written', 'Possibly AI-assisted', 'Clearly AI-generated', or 'Inconclusive'."},
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
            "text_analysis": {"indicators_found": [], "human_indicators_found": []},
            "cover_analysis": {"indicators_found": cover_indicators, "human_indicators_found": cover_human},
            "overall_assessment": {
                "conclusion": "Inconclusive",
                "explanation": "AI detection could not be completed"
            }
        }

def analyze_book_complete(text, cover_analysis, provided_title="", provided_author="", ai_verdict=None):
    """
    Complete book analysis with AI verdict-based penalty
    """
    if len(text) > 50000:
        text = text[:50000] + "... [truncated]"
    
    total_len = len(text)
    beginning = text[:min(5000, total_len//3)]
    middle = text[total_len//3:total_len//3*2][:5000]
    ending = text[-5000:]
    
    cover_text = ""
    if cover_analysis:
        cover_text = f"\nCOVER ANALYSIS:\n{json.dumps(cover_analysis, indent=2)}"
    
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
    
    # Genre rules
    genre_rules = """
    GENRE CLASSIFICATION RULES:
    - If personal story about author's own life → use "Memoir"
    - "Non-Fiction" ONLY for encyclopedias, textbooks, how-to books
    - DO NOT use "Non-Fiction" for memoirs
    - You can select MULTIPLE genres
    """
    
    allowed_genres_text = """
    ALLOWED GENRES (use ONLY these):
    - Romance, Fantasy, Romantasy, Science Fiction, Mystery, Thriller, Horror
    - Young Adult, Historical Fiction, Contemporary Fiction, Literary Fiction
    - Children's, Middle Grade, Non-Fiction, Memoir, Biography, Autobiography
    - Self-Help, LGBTQ+ Fiction, Paranormal, Graphic Novels, Comics
    - Classics, Erotica
    """
    
    prompt = f"""
    You are a professional literary analyst. Analyze THIS SPECIFIC BOOK based on the manuscript excerpts below.
    
    BOOK TITLE: {detected_title}
    AUTHOR: {detected_author}
    
    {cover_text}
    
    {genre_rules}
    {allowed_genres_text}
    
    EXCERPTS:
    BEGINNING: {beginning}
    MIDDLE: {middle}
    ENDING: {ending}
    
    Return JSON with marketability analysis.
    Score each category 0-100 based on writing quality, commercial potential, etc.
    
    Return JSON with these sections:
    {{
        "marketability": {{
            "overall_score": (0-100),
            "overall_grade": ("A", "B", "C", "D", "F" with +/-),
            "overall_assessment": "One sentence summary",
            "scores": {{
                "writing_quality": {{"score": 0-100, "explanation": ""}},
                "commercial_potential": {{"score": 0-100, "explanation": ""}},
                "genre_fit": {{"score": 0-100, "explanation": ""}},
                "hook_strength": {{"score": 0-100, "explanation": ""}},
                "character_appeal": {{"score": 0-100, "explanation": ""}},
                "pacing": {{"score": 0-100, "explanation": ""}},
                "originality": {{"score": 0-100, "explanation": ""}}
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
            "title": "{detected_title}",
            "author": "{detected_author}",
            "genres": [],
            "tone": "",
            "writing_style": "",
            "pacing_summary": ""
        }},
        "characters": {{
            "main": [],
            "supporting": [],
            "relationships": []
        }},
        "character_development": {{
            "protagonist_journey": "",
            "antagonist_motivation": "",
            "supporting_arcs": []
        }},
        "narrative_arc": {{
            "exposition": "",
            "rising_action": "",
            "climax": "",
            "falling_action": "",
            "resolution": ""
        }},
        "plot": {{
            "opening_hook": "",
            "inciting_incident": "",
            "major_plot_points": [],
            "plot_twists": []
        }},
        "themes": {{
            "primary": [],
            "secondary": []
        }},
        "strengths": [],
        "areas_for_improvement": [],
        "target_audience": {{
            "primary": "",
            "appeal": ""
        }},
        "marketing": {{
            "unique_selling_points": [],
            "blurb_suggestion": ""
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
        
        result = json.loads(response.choices[0].message.content)
        
        # Apply AI penalty if needed
        if ai_verdict:
            if ai_verdict == "Clearly AI-generated":
                # Severe penalty
                current = result['marketability']['overall_score']
                result['marketability']['overall_score'] = max(30, min(50, current - 40))
                result['marketability']['overall_grade'] = 'D'
                if 'areas_for_improvement' in result:
                    result['areas_for_improvement'].insert(0, "⚠️ Content shows clear signs of AI generation - needs authentic human voice")
                
            elif ai_verdict == "Possibly AI-assisted":
                # Moderate penalty
                current = result['marketability']['overall_score']
                result['marketability']['overall_score'] = max(50, min(65, current - 20))
                if 'areas_for_improvement' in result:
                    result['areas_for_improvement'].insert(0, "May have used AI assistance - needs more authentic voice")
        
        # Ensure title and author
        if 'book_info' not in result:
            result['book_info'] = {}
        result['book_info']['title'] = detected_title
        result['book_info']['author'] = detected_author
        
        return result
        
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        return None

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
    cover_data = ai_detection_results.get('cover_analysis', {})
    cover_indicators = cover_data.get('indicators_found', [])
    cover_human_indicators = cover_data.get('human_indicators_found', [])
    cover_verdict = cover_data.get('verdict', 'inconclusive')
    cover_confidence = cover_data.get('confidence', 0)
    
    # Determine styling based on conclusion
    conclusion_lower = ai_conclusion.lower()
    
    if 'human' in conclusion_lower:
        ai_bg = "#e8f5e8"
        ai_border = "#4caf50"
        ai_icon = "✍️✅"
        ai_title = "HUMAN-GENERATED CONTENT"
        ai_message = "This appears to be authentically human-written"
        ai_marketing_note = "Marketing Impact: This human-written quality is valuable - it helps create authentic emotional connections with readers and can be highlighted in marketing materials."
    elif 'clearly ai' in conclusion_lower or 'ai-generated' in conclusion_lower:
        ai_bg = "#ffebee"
        ai_border = "#f44336"
        ai_icon = "🤖⚠️"
        ai_title = "AI-GENERATED CONTENT"
        ai_message = "This book shows strong signs of AI generation"
        ai_marketing_note = "Marketing Impact: AI-generated content often struggles to connect with readers because it lacks authentic human voice and emotional depth. Consider revising to inject more unique voice and personal anecdotes."
    elif 'assisted' in conclusion_lower:
        ai_bg = "#fff3e0"
        ai_border = "#ff9800"
        ai_icon = "🤖❓"
        ai_title = "POSSIBLE AI ASSISTANCE"
        ai_message = "This book may have used AI assistance"
        ai_marketing_note = "Marketing Impact: If AI was used, ensure you've added enough of your unique voice and personal experience."
    else:
        ai_bg = "#f5f5f5"
        ai_border = "#999999"
        ai_icon = "❓"
        ai_title = "INCONCLUSIVE"
        ai_message = "AI detection analysis could not determine clearly"
        ai_marketing_note = "Marketing Impact: Consider getting a professional editorial review to assess the manuscript's authenticity."
    
    # Build cover verdict display
    if cover_verdict == "likely_ai":
        cover_display = f"LIKELY AI-GENERATED ({cover_confidence}% confidence)"
        cover_icon = "🤖⚠️"
    elif cover_verdict == "likely_human":
        cover_display = f"LIKELY HUMAN-DESIGNED ({cover_confidence}% confidence)"
        cover_icon = "🎨✅"
    else:
        cover_display = f"INCONCLUSIVE ({cover_confidence}% confidence)"
        cover_icon = "❓"
    
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
            .cover-badge {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
            }}
            .cover-ai {{
                background: #ffebee;
                color: #c62828;
            }}
            .cover-human {{
                background: #e8f5e8;
                color: #2e7d32;
            }}
            .cover-inconclusive {{
                background: #f5f5f5;
                color: #666;
            }}
        </style>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
            <h1>Your Complete Book Analysis</h1>
            <h2 style="font-size: 32px; margin: 10px 0;">{book_title}</h2>
            <h3 style="font-size: 20px; margin: 0 0 20px 0; opacity: 0.9;">by {author_name}</h3>
        </div>
        
        <!-- AI DETECTION SECTION - OVERALL -->
        <div class="ai-section">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{ai_icon}</span>
                <div>
                    <div class="ai-title">{ai_title}</div>
                </div>
            </div>
            
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {ai_message}</p>
            <p style="color: #555;">{ai_explanation}</p>
    """
    
    # Show text indicators
    if text_indicators or text_human_indicators:
        body += f"""
            <!-- Text Analysis -->
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">📝 Text Analysis:</p>
        """
        
        if text_indicators:
            body += f"""
                <p style="margin: 5px 0; color: #d32f2f;">⚠️ AI Indicators:</p>
                <ul style="margin: 0 0 15px 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_indicators[:5]])}
                </ul>
            """
        
        if text_human_indicators:
            body += f"""
                <p style="margin: 5px 0; color: #2e7d32;">✨ Human Qualities:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_human_indicators[:3]])}
                </ul>
            """
        
        body += "</div>"
    
    # Show cover indicators with verdict
    if cover_indicators or cover_human_indicators:
        body += f"""
            <!-- Cover Analysis with Verdict -->
            <div class="indicator-list">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 24px; margin-right: 10px;">{cover_icon}</span>
                    <div>
                        <p style="margin: 0; font-weight: bold;">🎨 Cover Analysis</p>
                        <p style="margin: 0; font-size: 14px;">
                            <span class="cover-badge cover-{cover_verdict.replace('likely_', '')}">{cover_display}</span>
                        </p>
                    </div>
                </div>
        """
        
        if cover_indicators:
            body += f"""
                <p style="margin: 10px 0 5px 0; color: #d32f2f;">⚠️ AI Indicators Found:</p>
                <ul style="margin: 0 0 15px 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_indicators[:5]])}
                </ul>
            """
        
        if cover_human_indicators:
            body += f"""
                <p style="margin: 5px 0; color: #2e7d32;">✨ Cover Strengths:</p>
                <ul style="margin: 0; color: #555;">
                    {''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_human_indicators[:3]])}
                </ul>
            """
        
        body += "</div>"
    
    # Marketing impact
    body += f"""
            <!-- Marketing Impact -->
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
    
    # Cover analysis style details
    if cover_analysis:
        body += f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin-top: 20px;">
            <h2>🎨 Cover Design Analysis</h2>
            <p><strong>Mood:</strong> {cover_analysis.get('mood', 'N/A')}</p>
            <p><strong>Genre Signals:</strong> {cover_analysis.get('genre_signals', 'N/A')}</p>
            <p><strong>Colors:</strong> {', '.join(cover_analysis.get('colors', ['N/A']))}</p>
            <p><strong>Composition:</strong> {cover_analysis.get('composition', 'N/A')}</p>
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
        .stFileUploader {
            padding: 10px;
        }
        .png-warning {
            background: #fff3cd;
            border-left: 5px solid #ff8800;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
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
        - 🤖 **AI detection analysis** - Find out if your book shows signs of AI generation (both text AND cover)
        - 📖 **Full book analysis** (genre, tone, writing style, pacing)
        - 📊 **Marketability score** with detailed breakdown
        - ✍️ **Writing quality assessment** (prose, dialogue, voice)
        - 👥 **Character analysis** (main characters and their roles)
        - 📈 **Narrative arc** (exposition, rising action, climax, resolution)
        - 🎯 **Theme identification** and motif analysis
        - 💪 **Key strengths** of your manuscript
        - 🔧 **Areas for improvement** with specific suggestions
        - 🎨 **Cover analysis with AI detection** (if you upload a PNG)
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
        st.markdown("**🎨 Cover Image (PNG only for best results)**")
        
        # PNG-only warning
        st.markdown("""
        <div class="png-warning">
            ⚠️ <strong>PNG files only</strong> - Other formats will be rejected<br>
            <small>PNG is lossless and gives most accurate AI detection</small>
        </div>
        """, unsafe_allow_html=True)
        
        cover = st.file_uploader(
            "Upload PNG only",
            type=['png'],  # ONLY PNG!
            key="cover",
            label_visibility="collapsed",
            help="Only PNG files are accepted for accurate AI detection"
        )
        if cover:
            st.success(f"✅ PNG file accepted: {cover.name}")
            # Store cover for later analysis
            st.session_state.cover_file = cover
    
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
                
                # Get verdict for penalty
                ai_verdict = ai_detection.get('overall_assessment', {}).get('conclusion')
                
                # Analyze manuscript with penalty
                analysis = analyze_book_complete(text, cover_analysis, book_title, author_name, ai_verdict)
                
                if analysis:
                    st.session_state.analysis_result = analysis
                    
                    # Get book title and author
                    book_info = analysis.get('book_info', {})
                    final_title = book_info.get('title', 'Your Book')
                    final_author = book_info.get('author', 'Unknown Author')
                    
                    # Send email
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

def extract_text_for_analysis(file):
    """Extract text for analysis only"""
    try:
        file_bytes = file.getvalue()
        
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in pdf_reader.pages[:20]:
                text += page.extract_text() + "\n"
            return text[:50000]
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = ""
            for para in doc.paragraphs[:1000]:
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
        
        else:
            return file_bytes.decode("utf-8", errors="ignore")[:50000]
            
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""

if __name__ == "__main__":
    show_marketability_checker()
