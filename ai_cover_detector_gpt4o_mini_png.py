# ai_cover_detector_gpt4o_mini_png.py - STREAMLIT VERSION (IDENTICAL LOGIC)
import streamlit as st
import base64
import os
from pathlib import Path
from PIL import Image
import io
from openai import OpenAI
import tempfile

# Initialize OpenAI with Streamlit secrets (ONLY CHANGE)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

def standardize_to_png(uploaded_file) -> tuple[bytes, str]:
    """Convert image or PDF first page to lossless PNG bytes"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        path = Path(tmp_path)
        
        # Handle PDF files
        if uploaded_file.type == "application/pdf":
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(str(path), first_page=1, last_page=1, dpi=250)
                if not images:
                    raise ValueError("No pages rendered from PDF")
                img = images[0]
            except ImportError:
                st.error("\nError: PDF support requires 'pdf2image' and poppler installed.")
                st.error("Install: pip install pdf2image")
                st.error("Poppler (Windows): https://github.com/oschwartz10612/poppler-windows/releases/")
                raise
            except Exception as e:
                raise RuntimeError(f"PDF conversion failed: {e}")
        else:
            try:
                img = Image.open(path)
                img = img.convert("RGB")  # remove alpha if present
            except Exception as e:
                raise RuntimeError(f"Cannot open image: {e}")

        # Save as PNG (lossless)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer.read(), "image/png"
        
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


def detect_ai_cover(png_bytes: bytes):
    b64 = base64.b64encode(png_bytes).decode("utf-8")

    prompt = """You are an expert at detecting AI-generated book covers.

Examine this image carefully for signs it was created by AI (Midjourney, DALL·E, Flux, Stable Diffusion, etc.).

Common strong AI indicators:
TEXT: gibberish letters, deformed/melted text, inconsistent fonts, spelling errors in title/author, text bleeding into background
ANATOMY: wrong number of fingers, fused/extra/missing limbs, asymmetrical faces, unnatural eye placement, plastic/smooth skin
DETAILS: hair/clothes/jewelry with illogical patterns, melted or repeating elements, missing micro-details (fur, pores, fabric texture)
LIGHT/SHADOW: inconsistent lighting sources, floating shadows, impossible reflections
COMPOSITION: overly symmetrical when it shouldn't be, objects blending unnaturally into background, gradient/stepping artifacts
OTHER: unnaturally saturated colors, dream-like smoothness everywhere, logical inconsistencies in scene

Be conservative: only classify as "likely AI" if you see **multiple clear red flags**.
If evidence is weak or mixed → say inconclusive.

Return **only** valid JSON:
{
  "verdict": "likely_ai" | "likely_human" | "inconclusive",
  "confidence": integer 0-100,
  "key_indicators": array of short strings describing what you saw,
  "explanation": one clear paragraph summary
}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]}
            ],
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        return response.choices[0].message.content

    except Exception as e:
        return f'{{"error": "OpenAI API error: {str(e)}"}}'
