import streamlit as st
import openai
import PyPDF2
import docx
import json
import base64
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re

# ────────────────────────────────────────────────
# Secrets (you fill these in Streamlit Cloud → Secrets)
# ────────────────────────────────────────────────
# In Streamlit Cloud: go to app → Settings → Secrets
# Paste something like this:
#
# OPENAI_API_KEY = "sk-..."
# SMTP_SERVER = "smtp.gmail.com"
# SMTP_PORT = 587
# SENDER_EMAIL = "your@gmail.com"
# SENDER_PASSWORD = "your-app-password"
# use_tls = true

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

SMTP_SERVER   = st.secrets["SMTP_SERVER"]
SMTP_PORT     = st.secrets["SMTP_PORT"]
SENDER_EMAIL  = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]
USE_TLS       = st.secrets.get("use_tls", True)
EDITOR_EMAIL  = "editor@bardspark.com"

# ────────────────────────────────────────────────
# Send email to user + editor
# ────────────────────────────────────────────────
def send_email(recipient_email, analysis_results, cover_analysis, book_title, author_name, word_count):
    """Send full analysis results via email - now with CC, word count, conditional banner"""
   
    subject = f"Your Complete Book Analysis: {book_title} by {author_name} (from {recipient_email})"
   
    marketability = analysis_results.get('marketability', {})
    score = marketability.get('overall_score', 'N/A')
    grade = marketability.get('overall_grade', 'N/A')
    book_info = analysis_results.get('book_info', {})
   
    # Conditional banner
    if isinstance(score, (int, float)) and score >= 70:
        conditional = """
        <div style="padding: 25px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 10px; margin: 25px 0; color: #155724; text-align: center;">
            <h2 style="margin: 0 0 15px 0;">🎉 Congratulations!</h2>
            <p style="font-size: 18px;">Your book has a marketability score of 70% or better.<br>We are happy to accept it for further marketing support.</p>
        </div>
        """
    else:
        conditional = """
        <div style="padding: 25px; background: #fff3cd; border: 1px solid #ffeeba; border-radius: 10px; margin: 25px 0; color: #856404;">
            <h2 style="margin: 0 0 15px 0;">⚠️ Your book needs more work</h2>
            <p>Most books sell only about 100 copies. A bad book will never sell.</p>
            <p><strong>For this reason we only accept books with a score of 70% or better for marketing support.</strong></p>
            <p>Your book needs more work. Please read the detailed analysis below to find areas of improvement.</p>
        </div>
        """
   
    # Start of body (your original header)
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

        <!-- Word count warning -->
        <div style="padding: 20px; background: #f8f9fa; border-radius: 10px; margin: 20px 0; border-left: 5px solid #667eea;">
            <h3>📏 Manuscript Length</h3>
            <p>Your manuscript is currently approximately <strong>{word_count:,}</strong> words long.</p>
            <p>A typical novel ranges from 70,000 to 100,000 words. If this is a partial manuscript or work in progress, the analysis has been performed on the provided content without penalizing the score for length.</p>
        </div>

        {conditional}

        <!-- Book Overview -->
        <div style="padding:24px; background:#f8f9fa; border-radius:12px; margin-bottom:30px;">
            <h2>📖 Book Overview</h2>
            <p><strong>Genre:</strong> {book_info.get('genre', 'Unknown')}</p>
            <p><strong>Tone:</strong> {book_info.get('tone', 'Unknown')}</p>
            <p><strong>Writing Style:</strong> {book_info.get('writing_style', 'Unknown')}</p>
            <p><strong>Pacing:</strong> {book_info.get('pacing_summary', 'Unknown')}</p>
        </div>

        <!-- Overall Assessment -->
        <div style="padding:24px; margin-bottom:30px;">
            <h2>📊 Overall Assessment</h2>
            <p>{marketability.get('overall_assessment', 'No summary available.')}</p>
        </div>

        <!-- Detailed Scores -->
        <div style="padding:24px; background:#f8f9fa; border-radius:12px; margin-bottom:30px;">
            <h2>📈 Detailed Scores</h2>
    """

    scores = marketability.get('scores', {})
    for key, data in scores.items():
        name = key.replace('_', ' ').title()
        val = data.get('score', 0)
        expl = data.get('explanation', 'No explanation')
        color = "#28a745" if val >= 80 else "#ffc107" if val >= 70 else "#fd7e14" if val >= 60 else "#dc3545"
        body += f"""
            <div style="margin-bottom:24px;">
                <div style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom:8px;">
                    {name} <span style="color:{color};">{val}</span>
                </div>
                <div style="height:14px; background:#e9ecef; border-radius:7px; overflow:hidden;">
                    <div style="width:{val}%; height:100%; background:{color}; transition:width 0.6s;"></div>
                </div>
                <p style="color:#555; font-size:15px; margin:10px 0 0 0;">{expl}</p>
            </div>
        """

    body += "</div>"

    # You can paste more sections here (characters, plot, themes, strengths, improvements, etc.)
    # For now keeping it shorter – add your original content if desired

    # Final message + CTA
    body += f"""
        <div style="padding:30px; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); border-radius:16px; color:white; text-align:center; margin:50px 0;">
            <h2 style="margin:0 0 25px 0; font-size:32px;">✅ Analysis Complete</h2>
            <p style="font-size:19px; margin:0 0 30px 0;">Full detailed report sent to <strong>{recipient_email}</strong></p>
            <p style="font-size:18px; margin:0 0 30px 0;">Ready to publish and promote your book?</p>
            <a href="https://bardspark.com/signup" style="background:white; color:#667eea; padding:16px 40px; text-decoration:none; border-radius:50px; font-weight:bold; font-size:18px; display:inline-block; box-shadow:0 4px 15px rgba(0,0,0,0.2);">
                SIGN UP FOR FREE →
            </a>
        </div>

        <p style="color:#777; font-size:14px; text-align:center; margin-top:50px;">
            Analysis performed on {datetime.now().strftime('%B %d, %Y')} | Sent to {recipient_email}
        </p>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Cc'] = EDITOR_EMAIL
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

# ────────────────────────────────────────────────
# Main app
# ────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Free Book Analysis", page_icon="📚", layout="wide")

    st.title("📊 Free One-Time Book Marketability Analysis")
    st.markdown("Upload your manuscript → receive a detailed professional analysis by email (one analysis per visitor / session)")

    # Session state keys
    for key in ['analysis_complete', 'analysis_result', 'text', 'word_count', 'book_title', 'author_name']:
        if key not in st.session_state:
            st.session_state[key] = False if key == 'analysis_complete' else None

    if not st.session_state.analysis_complete:
        show_upload()
    else:
        show_success()

def show_upload():
    col1, col2 = st.columns([5, 3])

    with col1:
        st.subheader("Manuscript file (PDF, DOCX or TXT)")
        manuscript = st.file_uploader(" ", type=["pdf", "docx", "txt"], label_visibility="collapsed")

        if manuscript is not None:
            with st.spinner("Reading file..."):
                text = extract_text(manuscript)
                st.session_state.text = text
                st.session_state.word_count = len(text.split()) if text else 0

            st.success(f"File loaded: {manuscript.name}")
            st.info(f"Your manuscript is currently approximately {st.session_state.word_count:,} words long. A typical novel ranges from 70,000 to 100,000 words. Note: If this is a partial manuscript or work in progress, the analysis will still be performed on the provided content without penalizing the score for length.")

    with col2:
        st.subheader("Cover image (optional)")
        cover = st.file_uploader(" ", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        if cover:
            st.image(cover, use_column_width=True)

    st.subheader("Optional – override detected title / author")
    title_input = st.text_input("Book title", "")
    author_input = st.text_input("Author name", "")

    st.markdown("---")
    email = st.text_input("📧 Email address (where we send the full report)", placeholder="your@email.com")

    if manuscript and email and st.session_state.text:
        if st.button("Analyze my book & send report", type="primary", use_container_width=True):
            with st.spinner("Analyzing (usually 50–90 seconds)..."):
                cover_analysis = None
                if cover:
                    try:
                        cover_bytes = cover.getvalue()
                        cover_b64 = base64.b64encode(cover_bytes).decode('utf-8')
                        cover_analysis = analyze_cover(cover_b64)
                    except:
                        pass

                text = st.session_state['text']
                word_count = st.session_state['word_count']
                analysis = analyze_book(text, cover_analysis, title_input, author_input)

                if analysis:
                    info = analysis.get('book_info', {})
                    st.session_state.book_title = info.get('title', 'Untitled')
                    st.session_state.author_name = info.get('author', 'Unknown')
                    st.session_state.analysis_result = analysis

                    sent = send_email(
                        email,
                        analysis,
                        cover_analysis,
                        st.session_state.book_title,
                        st.session_state.author_name,
                        word_count
                    )

                    if sent:
                        st.session_state.analysis_complete = True
                        st.rerun()
                    else:
                        st.error("Could not send email. Please try again.")
                else:
                    st.error("Analysis could not be completed. File may be too large or unreadable.")
    else:
        if not manuscript:
            st.info("Please upload your manuscript file first.")
        if not email:
            st.info("Please enter your email address.")

def show_success():
    st.success("✅ Analysis finished!")
    st.balloons()

    title = st.session_state.get('book_title', 'Your book')
    author = st.session_state.get('author_name', 'Unknown author')
    score = st.session_state.analysis_result.get('marketability', {}).get('overall_score', '—')

    st.markdown(f"**Book:** {title} by {author}")
    st.markdown(f"**Marketability score:** **{score}**")

    if isinstance(score, (int, float)) and score >= 70:
        st.success("Great score — congratulations!")
    else:
        st.warning("Score below 70 — more work needed before marketing.")

    st.markdown("---")
    st.markdown("**Full detailed report has been emailed to you.**")
    st.markdown("To analyze another book → refresh this page (Ctrl+R or F5)")

# ────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────

def extract_text(file):
    try:
        if file.type == "application/pdf":
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text

        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(file)
            return "\n".join(p.text for p in doc.paragraphs)

        else:  # txt
            return file.getvalue().decode("utf-8", errors="replace")

    except Exception as e:
        st.error(f"Could not read file: {str(e)}")
        return ""

def analyze_cover(b64):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this book cover in detail. Return **only** JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except:
        return None

def analyze_book(text, cover_analysis, custom_title, custom_author):
    if not text:
        return None

    # Truncate if huge
    if len(text) > 60000:
        text = text[:60000] + "\n[Text truncated due to length]"

    # Very basic title/author detection if not provided
    title = custom_title or "Untitled"
    author = custom_author or "Unknown Author"

    if not custom_title or not custom_author:
        lines = [l.strip() for l in text.splitlines() if l.strip()][:15]
        if lines:
            title = lines[0]
            for line in lines[1:]:
                if 'by ' in line.lower():
                    author = line.lower().split('by ')[-1].strip().title()
                    break

    prompt = f"""You are an expert book marketability analyst.

Title (use this): {title}
Author (use this): {author}

Analyze ONLY the text below. Be honest and specific.

Text excerpts:
{text[:15000]}

Return **valid JSON only** with at least these keys:
{{
  "book_info": {{"title": str, "author": str, "genre": str, "tone": str, "writing_style": str, "pacing_summary": str}},
  "marketability": {{
    "overall_score": number 0-100,
    "overall_grade": "A+/A/B+/B/C/D/F",
    "overall_assessment": "one sentence",
    "scores": {{ ... detailed scores with "score" and "explanation" ... }}
  }},
  ... other sections you had before (strengths, improvements, etc.)
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        result = json.loads(resp.choices[0].message.content)

        # Enforce correct title/author
        if 'book_info' in result:
            result['book_info']['title'] = title
            result['book_info']['author'] = author

        return result
    except Exception as e:
        st.error(f"LLM analysis failed: {str(e)}")
        return None

if __name__ == "__main__":
    main()
