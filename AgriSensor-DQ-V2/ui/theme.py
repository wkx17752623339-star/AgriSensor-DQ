from pathlib import Path
import streamlit as st

def apply():
 css=(Path(__file__).resolve().parents[1]/'assets'/'style.css').read_text(encoding='utf-8')
 st.markdown(f'<style>{css}</style>',unsafe_allow_html=True)

def heading(title,subtitle):
 st.markdown(f'<div class="page-head"><div class="eyebrow">AGRISENSOR · SMART AGRICULTURE</div><h1>{title}</h1><p>{subtitle}</p></div>',unsafe_allow_html=True)
