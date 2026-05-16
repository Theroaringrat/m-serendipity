import sys
sys.path.insert(0, '/home/yanbo_wang/.local/lib/python3.10/site-packages')

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import backend

# Page Config & Styling
st.set_page_config(layout="wide", page_title="M-Serendipity", page_icon="🏛️")

# Custom CSS for Dark Academia
st.markdown("""
<style>
    /* Dark Academia Theme */
    .stApp {
        background-color: #1a1a1a;
        color: #dcdccc;
        font-family: 'Garamond', serif;
    }
    h1, h2, h3 {
        font-family: 'Cinzel', serif;
        color: #c0a062; /* Gold/Bronze */
    }
    .stTextArea textarea {
        background-color: #2b2b2b;
        color: #dcdccc;
        border: 1px solid #c0a062;
    }
    .stButton button {
        background-color: #c0a062;
        color: #1a1a1a;
        border-radius: 5px;
        font-weight: bold;
    }
    .serendipity-card {
        background-color: #252525;
        border-left: 3px solid #c0a062;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .quote {
        font-style: italic;
        color: #a0a0a0;
    }
</style>
""", unsafe_allow_html=True)

# Application Header
st.title("🏛️ M-Serendipity")
st.markdown("### *Where Vibe Meets Intellect*")
st.markdown("Enter your academic passions, obscurities, and questions. We will find your intellectual kin.")

# Input Section
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("Your Personal Statement")
    student_input = st.text_area("What consumes your thoughts?", height=200, placeholder="e.g., I am fascinated by the ethics of memory in the digital age...")
    
    if st.button("Find Synergies"):
        if student_input:
            with st.spinner("Consulting the archives..."):
                recommendations = backend.get_recommendations(student_input)
                st.session_state['recommendations'] = recommendations
        else:
            st.warning("Please reveal your thoughts first.")

# Results
if 'recommendations' in st.session_state:
    recs = st.session_state['recommendations']

    with col1:
        st.subheader(“Serendipity Notes”)
        st.markdown(recs)
