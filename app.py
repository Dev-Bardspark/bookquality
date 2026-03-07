# BookMarketabilityChecker.py - FIXED VERSION WITH SEPARATE TEXT AND COVER AI DETECTION
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

# Import the PNG-only cover detector
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
    """
    Full cover analysis using the PERFECT PNG-only detector
    NO CONVERSION - only accepts PNG files directly
    """
    try:
        # Check if it's actually a PNG
        if cover_file.type != "image/png" and not cover_file.name.lower().endswith('.png'):
            st.error("❌ ONLY PNG FILES ARE ACCEPTED FOR COVER ANALYSIS")
            st.info("Please convert your image to PNG first (Paint, GIMP, or online converters)")
            return None
        
        # Get the PNG bytes directly - NO CONVERSION
        png_bytes = cover_file.getvalue()
        
        # Show what we're doing
        st.success("✅ PNG file accepted - analyzing...")
        
        # Detect AI using your PERFECT function
        ai_detection_json = ai_cover.detect_ai_cover(png_bytes)
        ai_detection_result = json.loads(ai_detection_json)
        
        # Also get style analysis (this is separate from AI detection)
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
        
        # Combine both analyses
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
    Analyze text and cover SEPARATELY for signs of AI generation
    Returns: dict with separate text and cover results, no combined overall
    """
    # Text detection prompt - no cover info included
    text_prompt = f"""
    You are an EXPERT forensic AI text detector. Your default stance is skeptical: polished, structured writing alone is NOT proof of human authorship — many current AI models produce exactly that.

    Analyze this manuscript excerpt VERY CRITICALLY for AI generation signs. You MUST look aggressively for subtle AI fingerprints even in professional-sounding text.

    MANUSCRIPT EXCERPT:
    {text[:15000]}  # Increased to 15k chars

    ===== STRONG AI INDICATORS (flag these aggressively) =====
    - Overly consistent tone without natural mood swings
    - Formulaic emotional language ("profound impact", "deep gratitude", "life-changing moment") used repeatedly
    - Lack of truly idiosyncratic / quirky personal details (real humans often include odd, specific, non-essential memories)
    - Predictable paragraph structure (setup → reflection → positive takeaway)
    - Absence of minor human imperfections (slight redundancy, unusual phrasing, informal asides)
    - Generic life-lesson summaries that feel inserted for inspiration
    - Overuse of abstract positive framing without concrete negative setbacks

    ===== STRONG HUMAN INDICATORS (require MULTIPLE and SPECIFIC) =====
    - Highly particular, sensory, non-generic details (exact prices, brand names, smells, small failures)
    - Self-deprecating or embarrassing admissions
    - Tangents / digressions that don't "serve" the narrative
    - Inconsistent but authentic voice (mix of formal and casual)
    - References to very specific historical / cultural micro-details

    ===== DECISION RULES — BE STRICT ON HUMAN CLAIMS =====
    - "Clearly AI-generated": Clear majority of indicators point to AI, weak or absent human markers
    - "Possibly AI-assisted": Mix — some human flavor but several AI-like patterns
    - "Likely human-written": MULTIPLE strong, specific human indicators AND very few AI patterns
    - "Inconclusive": Evidence is mixed or too thin

    Do NOT give "Likely human-written" just because the text is polished or has some emotion — require concrete, quirky, specific human evidence.

    Return JSON with ONLY text analysis:
    {{
        "text_analysis": {{
            "indicators_found": ["quote exact phrases/examples and explain why AI-like"],
            "human_indicators_found": ["quote exact phrases/examples and explain why human-like — be very selective"],
            "conclusion": ONE OF: "Clearly AI-generated", "Possibly AI-assisted", "Likely human-written", "Inconclusive",
            "explanation": "Detailed forensic reasoning — quote text, weigh both sides explicitly",
            "confidence": 0-100 integer based on strength of evidence
        }}
    }}
    """
    
    try:
        text_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a skeptical forensic AI detector. Modern LLMs can imitate human polish extremely well. Do not be impressed by structure, grammar, or emotion alone. Demand specific, idiosyncratic, slightly messy human evidence before concluding human authorship. Be more willing to call sophisticated AI text as AI or AI-assisted."},
                {"role": "user", "content": text_prompt}
            ],
            temperature=0.2,
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
        cover_result["conclusion"] = ai_detect.get('verdict', 'inconclusive')
        cover_result["confidence"] = ai_detect.get('confidence', 0)
        cover_result["explanation"] = ai_detect.get('explanation', '')
        if ai_detect.get('verdict') == "likely_human":
            cover_result["human_indicators_found"] = ["Professional design", "Consistent composition", "No AI artifacts"]
    
    return {
        "text": text_result,
        "cover": cover_result
    }

def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, ai_detection_results):
    """Send full analysis results via email with SEPARATE AI detection for text and cover"""
    
    subject = f"Your Complete Book Analysis: {book_title} by {author_name}"
    
    # Get marketability score
    marketability = analysis_results.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    
    # Format the email body with FULL analysis
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
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
    elif 'clearly ai' in text_lower or 'ai-generated' in text_lower:
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
    if cover_conclusion == "likely_ai":
        cover_bg = "#ffebee"
        cover_border = "#f44336"
        cover_icon = "🤖⚠️"
        cover_title = "COVER: AI-GENERATED"
        cover_message = "The cover shows signs of AI generation"
        cover_marketing_note = "Marketing Impact: AI covers can look generic; consider professional redesign."
    elif cover_conclusion == "likely_human":
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

    body = f"""
    <html>
    <head>
        <style>
            .ai-section {{
                background: #f8f9fa;
                border-left: 5px solid #ccc;
                padding: 20px;
                margin: 20px 0;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .ai-icon {{
                font-size: 24px;
                margin-right: 10px;
            }}
            .ai-title {{
                font-size: 18px;
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
        
        <!-- TEXT AI DETECTION SECTION -->
        <div class="ai-section" style="background: {text_bg}; border-left: 5px solid {text_border};">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{text_icon}</span>
                <div class="ai-title">{text_title} ({text_confidence}% confidence)</div>
            </div>
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {text_message}</p>
            <p style="color: #555;">{text_explanation}</p>
            
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">📝 Text Indicators:</p>
                {'<p style="margin: 5px 0; color: #d32f2f;">⚠️ AI Indicators:</p><ul style="margin: 0 0 15px 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_indicators[:5]]) + '</ul>' if text_indicators else ''}
                {'<p style="margin: 5px 0; color: #2e7d32;">✨ Human Qualities:</p><ul style="margin: 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in text_human_indicators[:3]]) + '</ul>' if text_human_indicators else ''}
            </div>
            
            <div class="marketing-impact" style="border-left: 3px solid {text_border};">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0; color: #333;">{text_marketing_note}</p>
            </div>
        </div>
        
        <!-- COVER AI DETECTION SECTION (if cover provided) -->
        {'' if not cover_analysis else f'''
        <div class="ai-section" style="background: {cover_bg}; border-left: 5px solid {cover_border};">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="ai-icon">{cover_icon}</span>
                <div class="ai-title">{cover_title} ({cover_confidence}% confidence)</div>
            </div>
            <p style="font-size: 16px; margin: 10px 0;"><strong>Analysis:</strong> {cover_message}</p>
            <p style="color: #555;">{cover_explanation}</p>
            
            <div class="indicator-list">
                <p style="margin: 0 0 10px 0; font-weight: bold;">🎨 Cover Indicators:</p>
                {'<p style="margin: 5px 0; color: #d32f2f;">⚠️ AI Indicators:</p><ul style="margin: 0 0 15px 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_indicators[:5]]) + '</ul>' if cover_indicators else ''}
                {'<p style="margin: 5px 0; color: #2e7d32;">✨ Human Qualities:</p><ul style="margin: 0; color: #555;">' + ''.join([f'<li style="margin: 5px 0;">{indicator}</li>' for indicator in cover_human_indicators[:3]]) + '</ul>' if cover_human_indicators else ''}
            </div>
            
            <div class="marketing-impact" style="border-left: 3px solid {cover_border};">
                <p style="margin: 0; font-weight: bold;">📢 Marketing Consideration:</p>
                <p style="margin: 5px 0 0 0; color: #333;">{cover_marketing_note}</p>
            </div>
        </div>
        '''}
        
        <!-- Marketability Score -->
        <div style="text-align: center; margin: 30px 0 20px 0;">
            <div style="font-size: 72px; font-weight: bold; color: #667eea;">{score}</div>
            <div style="font-size: 24px; color: #666;">Marketability Score ({grade})</div>
        </div>
    """
    
    # Rest of the body remains the same (book overview, assessment, etc.)
    # ... (omit for brevity, but include the full original body content here)
    
    # Note: Copy the remaining body content from the previous version, starting from Book Overview
    
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
    
    # Cover analysis style details (if available)
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

# The rest of the script remains the same, but update show_results_section to show separate banners

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
    text_lower = text_conclusion.lower()
    
    if 'human' in text_lower:
        text_bg_color = "#e8f5e8"
        text_border = "#4caf50"
        text_icon = "✍️✅"
        text_text = "TEXT: HUMAN-GENERATED"
    elif 'clearly ai' in text_lower or 'ai-generated' in text_lower:
        text_bg_color = "#ffebee"
        text_border = "#f44336"
        text_icon = "🤖⚠️"
        text_text = "TEXT: AI-GENERATED"
    elif 'assisted' in text_lower:
        text_bg_color = "#fff3e0"
        text_border = "#ff9800"
        text_icon = "🤖❓"
        text_text = "TEXT: POSSIBLE AI ASSISTANCE"
    else:
        text_bg_color = "#f5f5f5"
        text_border = "#999999"
        text_icon = "❓"
        text_text = "TEXT: INCONCLUSIVE"
    
    cover_ai = ai_detection.get('cover', {})
    cover_conclusion = cover_ai.get('conclusion', 'inconclusive')
    
    if cover_conclusion == "likely_ai":
        cover_bg_color = "#ffebee"
        cover_border = "#f44336"
        cover_icon = "🤖⚠️"
        cover_text = "COVER: AI-GENERATED"
    elif cover_conclusion == "likely_human":
        cover_bg_color = "#e8f5e8"
        cover_border = "#4caf50"
        cover_icon = "🎨✅"
        cover_text = "COVER: HUMAN-DESIGNED"
    else:
        cover_bg_color = "#f5f5f5"
        cover_border = "#999999"
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
    <div style="padding: 15px; background: {text_bg_color}; border-left: 5px solid {text_border}; border-radius: 5px; margin-bottom: 10px;">
        <div style="display: flex; align-items: center;">
            <span style="font-size: 24px; margin-right: 10px;">{text_icon}</span>
            <div>
                <strong>{text_text}</strong> ({text_ai.get('confidence', 0)}% confidence)<br>
                <span style="color: #666;">{text_ai.get('explanation', '')}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show COVER AI banner if cover was analyzed
    if st.session_state.cover_analysis:
        st.markdown(f"""
        <div style="padding: 15px; background: {cover_bg_color}; border-left: 5px solid {cover_border}; border-radius: 5px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center;">
                <span style="font-size: 24px; margin-right: 10px;">{cover_icon}</span>
                <div>
                    <strong>{cover_text}</strong> ({cover_ai.get('confidence', 0)}% confidence)<br>
                    <span style="color: #666;">{cover_ai.get('explanation', '')}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Rest of the results section remains the same
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

# The analyze_book_complete, show_marketability_checker, show_upload_section, extract_text_for_analysis functions remain the same as previous version.

if __name__ == "__main__":
    show_marketability_checker()
