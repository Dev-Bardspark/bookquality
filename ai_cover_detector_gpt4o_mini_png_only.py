# ai_cover_detector_gpt4o_mini_png_only.py
# Requirements:
#   pip install openai pillow python-magic
#   (no pdf2image or poppler needed anymore)

import base64
import os
from pathlib import Path
import streamlit as st
from PIL import Image
import io
from openai import OpenAI

# ────────────────────────────────────────
# CONFIG – Using Streamlit secrets
# ────────────────────────────────────────
client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)
MODEL = "gpt-4o-mini"
# ────────────────────────────────────────

def load_png_bytes(uploaded_file) -> bytes:
    """Load PNG file as bytes from Streamlit upload"""
    if uploaded_file.type != "image/png":
        raise ValueError("Only PNG files are accepted")
    
    return uploaded_file.getvalue()


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
