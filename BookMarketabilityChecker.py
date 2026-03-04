# BookMarketabilityChecker.py - STANDALONE FOR WEBSITE
import streamlit as st
from openai import OpenAI
import PyPDF2
import docx
import json
import base64
from PIL import Image
import io

# Initialize OpenAI with secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def show_marketability_checker():
    """Simple marketability checker for website homepage"""
    
    st.set_page_config(
        page_title="Is Your Book Ready to Sell?",
        page_icon="📊",
        layout="centered"
    )
    
    # Custom CSS for branding
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
        .cta-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 2rem;
            border-radius: 50px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-weight: bold;
            margin: 1rem 0;
            border: none;
            width: 100%;
        }
        .feature-box {
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #667eea;
        }
        .results-box {
            padding: 2rem;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: 2rem 0;
        }
        .signup-prompt {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin: 2rem 0;
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
    
    # Show upload section if no analysis yet
    if not st.session_state.analysis_result:
        show_upload_section()
    else:
        show_results_section()

def show_upload_section():
    """Show file upload interface"""
    
    st.markdown("""
    <div class="feature-box">
        <h3>📤 Upload your manuscript and cover</h3>
        <p>We'll analyze the first few pages to give you an honest marketability score.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📄 Manuscript**")
        manuscript = st.file_uploader(
            "Upload PDF, DOCX, or TXT",
            type=['pdf', 'docx', 'txt'],
            key="manuscript",
            label_visibility="collapsed"
        )
        if manuscript:
            st.success(f"✅ {manuscript.name}")
    
    with col2:
        st.markdown("**🎨 Cover Image**")
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
    
    if manuscript and cover:
        if st.button("🔍 GET MY MARKETABILITY SCORE", type="primary", use_container_width=True):
            with st.spinner("Analyzing your book... (about 45 seconds)"):
                
                # Extract text (first 5000 chars only for speed)
                text = extract_text_sample(manuscript, max_chars=5000)
                
                # Process cover
                cover_bytes = cover.getvalue()
                cover_base64 = base64.b64encode(cover_bytes).decode('utf-8')
                
                # Analyze cover
                cover_analysis = analyze_cover_simple(cover_base64)
                st.session_state.cover_analysis = cover_analysis
                
                # Analyze manuscript for marketability ONLY
                analysis = analyze_marketability(text, cover_analysis)
                
                st.session_state.analysis_result = analysis
                st.rerun()
    else:
        st.info("👆 Please upload both manuscript and cover to continue")

def show_results_section():
    """Show marketability results with call-to-action"""
    
    analysis = st.session_state.analysis_result
    
    # Extract marketability data
    marketability = analysis.get('marketability', {})
    overall_score = marketability.get('overall_score', 0)
    overall_grade = marketability.get('overall_grade', 'N/A')
    overall_assessment = marketability.get('overall_assessment', '')
    
    # Color based on score
    if overall_score >= 80:
        bg_color = "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)"
        emoji = "🚀"
        message = "Your book has EXCELLENT marketability potential!"
    elif overall_score >= 70:
        bg_color = "linear-gradient(135deg, #f7971e 0%, #ffd200 100%)"
        emoji = "📈"
        message = "Your book has GOOD marketability potential!"
    elif overall_score >= 60:
        bg_color = "linear-gradient(135deg, #ff6b6b 0%, #feca57 100%)"
        emoji = "📊"
        message = "Your book has FAIR marketability potential."
    else:
        bg_color = "linear-gradient(135deg, #ff4b4b 0%, #ff9f4b 100%)"
        emoji = "⚠️"
        message = "Your book NEEDS WORK before marketing."
    
    # Show score prominently
    st.markdown(f"""
    <div class="score-box" style="background: {bg_color};">
        <p class="score-number">{overall_score}</p>
        <p class="score-label">Marketability Score</p>
        <p style="font-size: 18px; margin-top: 10px;">Grade: {overall_grade} {emoji}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"**{message}**")
    st.markdown(f"*{overall_assessment}*")
    
    st.markdown("---")
    
    # Show quick breakdown
    st.markdown("### 📊 Quick Breakdown")
    
    scores = marketability.get('scores', {})
    if scores:
        col1, col2 = st.columns(2)
        
        score_items = list(scores.items())[:6]  # Show first 6 scores
        for i, (score_name, score_data) in enumerate(score_items):
            display_name = score_name.replace('_', ' ').title()
            score_value = score_data.get('score', 0)
            
            with col1 if i % 2 == 0 else col2:
                st.markdown(f"""
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span>{display_name}</span>
                        <span style="font-weight: bold;">{score_value}</span>
                    </div>
                    <div style="height: 6px; background: #eee; border-radius: 3px;">
                        <div style="width: {score_value}%; height: 6px; background: #667eea; border-radius: 3px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Cover analysis summary
    if st.session_state.cover_analysis:
        cover = st.session_state.cover_analysis
        st.markdown("### 🎨 Cover Insights")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Strengths**")
            for s in cover.get('strengths', [])[:2]:
                st.write(f"✅ {s}")
        with col2:
            st.markdown("**Weaknesses**")
            for w in cover.get('weaknesses', [])[:2]:
                st.write(f"⚠️ {w}")
    
    st.markdown("---")
    
    # Call to action - SIGN UP FOR FULL ACCESS
    st.markdown("""
    <div class="signup-prompt">
        <h2>✨ Want the complete analysis?</h2>
        <p style="font-size: 18px;">Get access to:</p>
        <p>📖 Full literary analysis</p>
        <p>🎨 Detailed cover feedback</p>
        <p>📈 Competitor comparison</p>
        <p>🎯 Target audience insights</p>
        <p>📋 Custom marketing plan</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col2:
        if st.button("🚀 SIGN UP FOR FULL ACCESS", type="primary", use_container_width=True):
            # Link to your main app signup
            st.markdown("[Click here to sign up](https://yourapp.com)")
    
    # Option to try another book
    if st.button("🔄 Analyze Another Book", use_container_width=True):
        st.session_state.analysis_result = None
        st.session_state.cover_analysis = None
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
        "weaknesses": ["2 specific weaknesses"]
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
        return {
            "colors": ["Unable to analyze"],
            "has_figure": False,
            "mood": "Unknown",
            "genre_signals": "Unknown",
            "strengths": ["Try again"],
            "weaknesses": ["Image may be invalid"]
        }

def analyze_marketability(text, cover_analysis):
    """Simple marketability-only analysis"""
    
    prompt = f"""
    Based on this manuscript excerpt and cover, provide a marketability analysis.
    
    COVER ANALYSIS:
    {json.dumps(cover_analysis, indent=2)}
    
    MANUSCRIPT EXCERPT:
    {text[:3000]}
    
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

def extract_text_sample(file, max_chars=5000):
    """Extract first part of text from uploaded file"""
    try:
        if file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages[:3]:  # First 3 pages only
                text += page.extract_text()
            return text[:max_chars]
            
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            text = ""
            for para in doc.paragraphs[:50]:  # First 50 paragraphs
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
