import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
import re
from PyPDF2 import PdfReader
import docx
import nltk
from nltk.corpus import stopwords
import io
import random

# Download stopwords if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('punkt_tab')

def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_txt(file):
    return file.getvalue().decode("utf-8")

def clean_text(text):
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    # Remove non-alphanumeric characters but keep spaces
    text = re.sub(r'[^\w\s]', '', text)
    return text.lower()

def get_top_words(text, n=50):
    # Tokenize
    words = nltk.word_tokenize(text)
    
    # Get English stopwords
    stop_words = set(stopwords.words('english'))
    
    # Filter out stopwords and short words
    filtered_words = [word for word in words if word.lower() not in stop_words and len(word) > 2]
    
    # Count frequencies
    word_freq = Counter(filtered_words)
    
    # Get top n words
    top_words = word_freq.most_common(n)
    
    return top_words

def main():
    st.title("Book Word Frequency Analyzer")
    st.write("Upload a book (PDF, DOCX, or TXT) to see the most frequent words.")
    
    # File uploader - added key parameter
    uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx', 'txt'], key="file_uploader")
    
    if uploaded_file is not None:
        # Check if this is a new file
        if 'current_file' not in st.session_state or st.session_state.current_file != uploaded_file.name:
            st.session_state.current_file = uploaded_file.name
            st.session_state.analysis_done = False
        
        # Only analyze if not already done for this file
        if not st.session_state.get('analysis_done', False):
            with st.spinner("Analyzing the book..."):
                try:
                    # Extract text based on file type
                    if uploaded_file.type == "application/pdf":
                        text = extract_text_from_pdf(uploaded_file)
                    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                        text = extract_text_from_docx(uploaded_file)
                    else:  # txt file
                        text = extract_text_from_txt(uploaded_file)
                    
                    # Clean the text
                    cleaned_text = clean_text(text)
                    
                    # Get top words
                    top_words = get_top_words(cleaned_text, 50)
                    
                    # Store in session state
                    st.session_state.top_words = top_words
                    st.session_state.analysis_done = True
                    
                    # Create DataFrame for display
                    word_data = pd.DataFrame(top_words, columns=['Word', 'Frequency'])
                    st.session_state.word_data = word_data
                    
                    st.success("Analysis complete!")
                    
                except Exception as e:
                    st.error(f"Error analyzing file: {str(e)}")
                    return
        
        # Display results
        if 'word_data' in st.session_state:
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Unique Words", len(st.session_state.top_words))
            with col2:
                st.metric("Most Frequent Word", st.session_state.top_words[0][0])
            with col3:
                st.metric("Top Word Frequency", st.session_state.top_words[0][1])
            
            # Display table
            st.subheader("Top 50 Most Frequent Words")
            st.dataframe(st.session_state.word_data, use_container_width=True)
            
            # Create visualization
            st.subheader("Word Frequency Distribution")
            fig = px.bar(st.session_state.word_data, 
                        x='Word', 
                        y='Frequency',
                        title="Top 50 Words by Frequency",
                        labels={'Frequency': 'Number of Occurrences'})
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Download button for results
            csv = st.session_state.word_data.to_csv(index=False)
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name=f"word_frequency_{st.session_state.current_file}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
