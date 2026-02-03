import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

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
    h1 {{ color: {TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; font-size: 40px; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; letter-spacing: 2px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 15px; width: 100%; font-weight: bold; text-transform: uppercase; transition: 0.3s; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
    .stFileUploader label {{ color: {PRIMARY_COLOR}; font-weight: bold; }}
    .stSuccess {{ background-color: rgba(197, 160, 89, 0.2); border-left: 5px solid {PRIMARY_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. TEXT ENGINE (PILLOW REPLACEMENT) ---
def create_pil_text_clip(text, font_path, font_size, color, stroke_width=2, stroke_color='black'):
    """
    Generates a transparent text image using PIL (Pillow) instead of ImageMagick.
    This bypasses all Linux security policy errors.
    """
    # 1. Load Font
    try:
        if font_path:
            font = ImageFont.truetype(font_path, font_size)
        else:
            # Fallback for Linux servers if no font provided
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        # Ultimate fallback
        font = ImageFont.load_default()

    # 2. Calculate Text Size using getbbox
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    # Get bounding box [left, top, right, bottom]
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Add some padding so strokes don't get cut off
    width = text_width + 40
    height = text_height + 40

    # 3. Create Image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 4. Draw Text (Centered)
    # Note: simple centering logic
    x = 20
    y = 20
    
    draw.text((x, y), text, font=font, fill=color, align='center', 
              stroke_width=stroke_width, stroke_fill=stroke_color)

    # 5. Convert to MoviePy ImageClip
    return ImageClip(np.array(img))

# --- 5. VIDEO BATCH PROCESSOR ---
def process_video_batch(df, video_path, font_path, temp_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    clip = VideoFileClip(video_path)
    
    for i, row in df.iterrows():
        city_name = str(row['City']).upper()
        status_text.markdown(f"**PROCESSING:** {city_name}")
        
        # --- TEXT LAYERS (Using New PIL Engine) ---
        
        # 1. BAND NAME
        txt1 = create_pil_text_clip(
            "LAWRENCE\nWITH JACOB JEFFRIES", 
            font_path, 80, 'white', stroke_width=3
        )
        txt1 = txt1.set_position(('center', 'center')).set_start(0).set_duration(4)

        # 2. DATE/VENUE
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}"
        txt2 = create_pil_text_clip(
            content2.upper(), 
            font_path, 70, 'white', stroke_width=3
        )
        txt2 = txt2.set_position(('center', 'center')).set_start(4).set_duration(13)

        # 3. LINK
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}"
        txt3 = create_pil_text_clip(
            content3.upper(), 
            font_path, 70, 'white', stroke_width=3
        )
        txt3 = txt3.set_position(('center', 'center')).set_start(17).set_duration(clip.duration - 17)
        
        # COMPOSITE
        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        
        output_filename = f"Promo_{city_name.replace(' ', '')}.mp4"
        output_path = os.path.join(temp_dir, output_filename)
        
        # RENDER
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        
        generated_paths.append(output_path)
        progress_bar.progress((i + 1) / len(df))
        
    clip.close()
    return generated_paths

# --- 6. FRONT END INTERFACE ---
st.title("VID_LOCAL")
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ASSETS")
        uploaded_video = st.file_uploader("Clean Video File (.mp4)", type=["mp4"])
        uploaded_font = st.file_uploader("Font File (.ttf) [Recommended]", type=["ttf"])
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
