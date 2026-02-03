import streamlit as st
import os
import shutil

# --- IMAGEMAGICK CLOUD FIX (MUST RUN BEFORE MOVIEPY) ---
# This overrides the server's strict security policy to allow text generation
def fix_imagemagick_policy():
    # Define the path to the system policy
    system_policy_path = "/etc/ImageMagick-6/policy.xml"
    local_policy_path = os.path.join(os.getcwd(), "policy.xml")
    
    # Only run this if we are on the cloud (Linux) and haven't fixed it yet
    if os.path.exists(system_policy_path) and not os.path.exists(local_policy_path):
        with open(system_policy_path, "r") as f:
            policy_content = f.read()
        
        # Replace the blocking rule (rights="none" -> rights="read|write")
        fixed_content = policy_content.replace('rights="none" pattern="@*"', 'rights="read|write" pattern="@*"')
        
        # Save the fixed version locally
        with open(local_policy_path, "w") as f:
            f.write(fixed_content)
    
    # If we created a local policy, tell ImageMagick to use it
    if os.path.exists(local_policy_path):
        os.environ["MAGICK_CONFIGURE_PATH"] = os.getcwd()

fix_imagemagick_policy()
# -------------------------------------------------------

import pandas as pd
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import tempfile
import zipfile

# --- 1. BRANDING CONFIGURATION ---
APP_NAME = "vid_local"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#C5A059"  # Cinema Gold
BACKGROUND_COLOR = "#0e0e0e"
TEXT_COLOR = "#ffffff"

# --- 2. PAGE SETUP ---
st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

# --- 3. CUSTOM CSS ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; font-family: 'Helvetica Neue', sans-serif; }}
    h1 {{ color: {TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 15px; width: 100%; font-weight: bold; transition: 0.3s; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. VIDEO ENGINE ---
def process_video_batch(df, video_path, font_path, temp_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    clip = VideoFileClip(video_path)
    font_to_use = font_path if font_path else 'Arial'
    
    for i, row in df.iterrows():
        city_name = str(row['City']).upper()
        status_text.markdown(f"**PROCESSING:** {city_name}")
        
        # 1. BAND NAME
        txt1 = TextClip("LAWRENCE\nWITH JACOB JEFFRIES", font=font_to_use, fontsize=80, color='white', stroke_color='black', stroke_width=2)
        txt1 = txt1.set_position(('center', 'center')).set_start(0).set_duration(4)

        # 2. DATE/VENUE
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}"
        txt2 = TextClip(content2.upper(), font=font_to_use, fontsize=70, color='white', stroke_color='black', stroke_width=2)
        txt2 = txt2.set_position(('center', 'center')).set_start(4).set_duration(13)

        # 3. LINK
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}"
        txt3 = TextClip(content3.upper(), font=font_to_use, fontsize=70, color='white', stroke_color='black', stroke_width=2)
        txt3 = txt3.set_position(('center', 'center')).set_start(17).set_duration(clip.duration - 17)
        
        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        
        output_filename = f"Promo_{city_name.replace(' ', '')}.mp4"
        output_path = os.path.join(temp_dir, output_filename)
        
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        
        generated_paths.append(output_path)
        progress_bar.progress((i + 1) / len(df))
        
    clip.close()
    return generated_paths

# --- 5. FRONT END ---
st.title("VID_LOCAL")
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ASSETS")
        uploaded_video = st.file_uploader("Clean Video File (.mp4)", type=["mp4"])
        uploaded_font = st.file_uploader("Font File (.ttf) [Optional]", type=["ttf"])
    with col2:
        st.markdown("#### DATA")
        uploaded_csv = st.file_uploader("Tour Schedule (.csv)", type=["csv"])

if uploaded_video and uploaded_csv:
    st.markdown("---")
    if st.button("INITIALIZE RENDER ENGINE"):
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # Save Inputs
            tfile_vid = os.path.join(temp_dir, "input.mp4")
            with open(tfile_vid, "wb") as f: f.write(uploaded_video.read())
            
            font_path = None
            if uploaded_font:
                font_path = os.path.join(temp_dir, "custom.ttf")
                with open(font_path, "wb") as f: f.write(uploaded_font.read())
            
            try:
                # Run Generation
                files = process_video_batch(pd.read_csv(uploaded_csv), tfile_vid, font_path, temp_dir)
                
                # Zip
                zip_path = os.path.join(temp_dir, f"{APP_NAME}_Output.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in files:
                        zipf.write(file, os.path.basename(file))
                
                st.balloons()
                st.success("RENDER COMPLETE.")
                with open(zip_path, "rb") as f:
                    st.download_button("⬇️ DOWNLOAD ZIP PACKAGE", f, f"{APP_NAME}_Assets.zip", "application/zip")
                    
            except Exception as e:
                st.error(f"Render Error: {str(e)}")
