# ai_text_detector_gpt4o_mini_simple_labels.py
# Requirements:
#   pip install openai python-docx pymupdf   # pymupdf = fitz for PDFs
#
# Modified to work with Streamlit secrets

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai not installed → pip install openai")
    sys.exit(1)

# Try to import streamlit for secrets, but don't require it
try:
    import streamlit as st
    USING_STREAMLIT = True
except ImportError:
    USING_STREAMLIT = False

# ────────────────────────────────────────
# CONFIG – Will use Streamlit secrets if available, otherwise use hardcoded key
# ────────────────────────────────────────
def get_api_key():
    """Get API key from Streamlit secrets if available, otherwise from hardcoded variable"""
    if USING_STREAMLIT and hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    else:
        # Fallback to hardcoded key for standalone use
        # IMPORTANT: Replace this with your key or set environment variable OPENAI_API_KEY
        return os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY_HERE")

# Initialize client only when needed (lazy initialization)
_client = None

def get_client():
    """Get or create OpenAI client"""
    global _client
    if _client is None:
        api_key = get_api_key()
        if api_key == "YOUR_API_KEY_HERE" or not api_key:
            raise ValueError("OpenAI API key not found. Please set it in Streamlit secrets or as OPENAI_API_KEY environment variable.")
        _client = OpenAI(api_key=api_key)
    return _client

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2
MAX_CHARS = 45000

# ────────────────────────────────────────
def extract_text_from_file(file_path: str) -> str:
    """Extract text from various file formats"""
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext in [".txt", ".md", ".markdown"]:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read().strip()

        elif ext == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
            except ImportError:
                raise RuntimeError("python-docx not installed → pip install python-docx")

        elif ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(path)
                text = ""
                for page in doc:
                    text += page.get_text("text") + "\n"
                doc.close()
                return text.strip()
            except ImportError:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(path)
                    text = ""
                    for page in reader.pages:
                        text += (page.extract_text() or "") + "\n"
                    return text.strip()
                except ImportError:
                    raise RuntimeError("No PDF reader → pip install pymupdf   OR   pip install pypdf")

        else:
            raise ValueError(f"Unsupported file type: {ext}\nSupported: .txt, .md, .docx, .pdf")

    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {file_path}:\n{str(e)}")

# ────────────────────────────────────────
def detect_ai_text(raw_text: str, client_override=None):
    """
    Detect if text is AI-generated
    
    Args:
        raw_text: The text to analyze
        client_override: Optional OpenAI client override (for testing)
    
    Returns:
        dict with detection results
    """
    text = raw_text[:MAX_CHARS].strip()
    if len(text) < 400:
        return {"error": "Text too short (<400 chars) — cannot judge reliably"}

    prompt = """You are an expert at distinguishing authentic human long-form writing from current AI-generated or heavily AI-assisted text.

Focus on the HARDEST-TO-FAKE signals only:
• Concrete, lived-in, sensory or hyper-specific personal details that feel idiosyncratic
• Natural emotional unevenness: small frustrations, ambivalence, self-deprecation, petty complaints
• Slightly awkward / non-optimal / quirky phrasing, unusual metaphors or word choices
• Mundane/irrelevant micro-details that don't push plot or theme forward
• Absence of constant uplift / inspiration / balanced symmetry in tone

Be VERY conservative: only say "likely AI" if you see **multiple strong, specific red flags**.
Mixed / average polished writing → "inconclusive".
Strong authentic human markers → "likely human".

Return **only** valid JSON:
{
  "verdict": "likely_ai" | "likely_human" | "inconclusive",
  "confidence": integer 0-100,
  "key_indicators": array of short strings (quote 1–8 word phrases from text when possible),
  "explanation": one clear paragraph (max 90 words)
}
"""

    try:
        # Use provided client or get default
        client = client_override if client_override else get_client()
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": f"{prompt}\n\nTEXT TO ANALYZE:\n\n{text}"}],
            temperature=TEMPERATURE,
            max_tokens=450,
            response_format={"type": "json_object"}
        )
        result_str = response.choices[0].message.content
        parsed = json.loads(result_str)

        # Map to simple display label only
        verdict = parsed.get("verdict", "inconclusive")
        conf = parsed.get("confidence", 50)

        if verdict == "likely_ai":
            display_label = "Probably AI"
        elif verdict == "likely_human":
            display_label = "Probably Human"
        else:
            display_label = "Inconclusive"

        return {
            "display_label": display_label,
            "raw_verdict": verdict,
            "confidence": conf,
            "key_indicators": parsed.get("key_indicators", []),
            "explanation": parsed.get("explanation", "No explanation available"),
            "model_used": MODEL
        }

    except Exception as e:
        error = {"error": f"OpenAI API error: {str(e)}"}
        return error

# ────────────────────────────────────────
def main():
    """Standalone mode with GUI"""
    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo("AI Text Detector", 
                        "Select your manuscript (.txt, .md, .docx, .pdf)\n\n"
                        "Result will be: Probably AI / Probably Human / Inconclusive\n"
                        "Full justification shown in console.")

    file_path = filedialog.askopenfilename(
        title="Select manuscript file",
        filetypes=[
            ("Supported files", "*.txt *.md *.markdown *.docx *.pdf"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        print("No file selected. Exiting.")
        return

    print(f"Selected: {file_path}")
    print("-" * 80)

    try:
        text_content = extract_text_from_file(file_path)
        print(f"Extracted ≈ {len(text_content):,} characters")
        print("Running AI detection...\n")

        result = detect_ai_text(text_content)

        if "error" in result:
            print(f"ERROR: {result['error']}")
            messagebox.showerror("Error", result['error'])
            return

        print("\n" + "="*90)
        print("FINAL RESULT:")
        print(f"→ {result['display_label']}")
        print("\nFULL JUSTIFICATION:")
        print(f"Raw verdict from model: {result['raw_verdict']}")
        print(f"Confidence score: {result['confidence']}%")
        print("\nKey indicators / quoted phrases:")
        for ind in result['key_indicators']:
            print(f"• {ind}")
        print("\nModel explanation:")
        print(result['explanation'])
        print("="*90)

        messagebox.showinfo("Detection Complete", 
                            f"Result: {result['display_label']}\n\n"
                            "Full justification (raw verdict, confidence, indicators, explanation) is printed in the console.")

    except Exception as e:
        messagebox.showerror("Error", str(e))
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
