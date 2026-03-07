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

# Load CSS
def load_css():
    with open('styles.css', 'r') as f:
        css = f.read()
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

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
    
    FIXED: Much more balanced detection that won't flag human text as AI
    """
    # Text detection prompt - MUCH more balanced and forgiving
    text_prompt = f"""
    You are an expert forensic AI text detector. Your analysis must be BALANCED and FAIR.
    
    IMPORTANT GUIDELINES:
    1. DO NOT flag polished, well-structured writing as AI. Many skilled human writers produce clean prose.
    2. DO NOT flag emotional content or inspirational themes as AI. Humans write about emotions too.
    3. DO NOT flag consistent tone as AI. Many authors maintain consistent voice throughout their work.
    4. Only flag text as AI if you find MULTIPLE clear, undeniable AI artifacts.
    5. When in doubt, err on the side of "Likely human-written" or "Inconclusive".
    
    MANUSCRIPT EXCERPT:
    {text[:15000]}
    
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
    
    ===== DECISION RULES — BE LIBERAL WITH HUMAN CLASSIFICATION =====
    - "Clearly AI-generated": Multiple undeniable AI patterns, NO human indicators
    - "Possibly AI-assisted": Some AI patterns but also some human elements
    - "Likely human-written": Clear human voice and authenticity, even if polished
    - "Inconclusive": Evidence is mixed or insufficient
    
    Remember: Professional human writing often looks "too perfect" to the untrained eye.
    Do NOT penalize quality writing. Look for genuine AI artifacts, not just good prose.
    
    Return JSON with ONLY text analysis:
    {{
        "text_analysis": {{
            "indicators_found": ["quote exact phrases and explain why they might be AI-like — be selective"],
            "human_indicators_found": ["quote exact phrases and explain why they're clearly human"],
            "conclusion": ONE OF: "Clearly AI-generated", "Possibly AI-assisted", "Likely human-written", "Inconclusive",
            "explanation": "Detailed reasoning — be fair and balanced, explain why you reached this conclusion",
            "confidence": 0-100 integer based on strength of evidence
        }}
    }}
    """
    
    try:
        text_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a fair and balanced forensic AI detector. 
                Your default assumption is that text is human-written unless you find overwhelming evidence otherwise.
                Professional human writing can be polished, emotional, and well-structured. Do not penalize quality.
                Only flag text as AI if you find clear, undeniable AI artifacts that couldn't come from a skilled human writer.
                When in doubt, classify as 'Likely human-written' or 'Inconclusive'."""},
                {"role": "user", "content": text_prompt}
            ],
            temperature=0.3,  # Slightly higher temperature for more balanced responses
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        text_result = json.loads(text_response.choices[0].message.content)["text_analysis"]
        
        # Post-process to ensure we're not being too harsh
        if text_result["conclusion"] in ["Clearly AI-generated", "Possibly AI-assisted"]:
            # Double-check: if confidence is below 70%, downgrade to Inconclusive
            if text_result["confidence"] < 70:
                text_result["conclusion"] = "Inconclusive"
                text_result["explanation"] += " [Confidence too low for definitive AI classification]"
            
            # Also check: if there are ANY human indicators, consider downgrading
            if len(text_result.get("human_indicators_found", [])) > 0:
                if text_result["conclusion"] == "Clearly AI-generated":
                    text_result["conclusion"] = "Possibly AI-assisted"
                    text_result["explanation"] += " [Downgraded due to presence of human indicators]"
        
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
            cover_result["human_indicators_found"] = ["Professional design", "Consistent composition", "No AI artifacts"]
    
    return {
        "text": text_result,
        "cover": cover_result
    }

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

# [Rest of your functions remain the same - show_upload_section(), show_results_section(), 
# extract_text_for_analysis(), analyze_book_complete(), etc.]

if __name__ == "__main__":
    show_marketability_checker()
