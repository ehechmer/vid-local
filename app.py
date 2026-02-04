import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

#---1. BRANDING CONFIGURATION
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"
BACKGROUND_COLOR = "#0A1A1E"
TEXT_COLOR = "#DCE4EA"

#---2. PAGE SETUP
st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

#---3. CUSTOM CSS (Wrapped for stability)
st.markdown(f"""
<style>
    .stApp {{ background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; font-family: 'Helvetica Neue', sans-serif; }}
    h1 {{ color: {TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; font-size: 40px; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; letter-spacing: 2px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 10px; width: 100%; font-weight: bold; text-transform: uppercase; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
</style>
""", unsafe_allow_html=True)

#---4. TEXT ENGINE (PILLOW)
def create_pil_text_clip(text, font_path, font_size, color, stroke_width=3, stroke_color='black'):
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, int(font_size))
        else:
            try:
                # Standard path for Streamlit Cloud (Debian)
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(font_size))
            except:
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width)
    
    width, height = int((bbox[2] - bbox[0]) + 60), int((bbox[3] - bbox[1]) + 60)
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((int(30 - bbox[0]), int(30 - bbox[1])), text, font=font, fill=color, align='center', 
              stroke_width=stroke_width, stroke_fill=stroke_color)
    return ImageClip(np.array(img))

#---5. CORE RENDERING ENGINE
def render_video(row, videos_dir, font_path, output_path):
    filename = row.get('Filename', None)
    video_full_path = os.path.join(videos_dir, str(filename))

    if not filename or not os.path.exists(video_full_path):
        return None

    city_name = str(row.get('City', 'Unknown')).upper()
    clip = VideoFileClip(video_full_path)
    w, h = clip.size
    duration = clip.duration
    scale = 1.0 if (w / h) < 0.7 else 0.75

    # Animation Settings
    slide_speed = 0.5 
    travel_distance = 50 
    
    # Layer 1: Band Name
    txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(80 * scale), 'white')
    txt1 = txt1.set_position(('center', 'center')).set_start(0).set_duration(duration * 0.20).crossfadeout(0.3)

    # Layer 2: Date & City (Slide Up)
    content2 = f"{row.get('Date', '')}\n{city_name}\n{row.get('Venue', '')}".upper()
    txt2 = create_pil_text_clip(content2, font_path, int(70 * scale), 'white')
    txt2 = txt2.set_position(lambda t: ('center', (h/2 + travel_distance) - (min(1, t/slide_speed) * travel_distance)))
    txt2 = txt2.set_start(duration * 0.20).set_duration(duration * 0.65).crossfadein(0.3)

    # Layer 3: Link
    content3 = f"TICKETS ON SALE NOW\n{row.get('Ticket_Link', '')}".upper()
    txt3 = create_pil_text_clip(content3, font_path, int(70 * scale), 'white')
    txt3 = txt3.set_position(('center', 'center')).set_start(duration * 0.85).set_duration(duration * 0.15).crossfadein(0.2)

    final = CompositeVideoClip([clip, txt1, txt2, txt3])
    final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
    clip.close()
    return output_path

#---6. FRONT END
st.title(APP_NAME)
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### 1. ASSETS")
    uploaded_zip = st.file_uploader("Upload ZIP of Raw Videos", type=["zip"])
    uploaded_font = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
with col2:
    st.markdown("#### 2. DATA")
    uploaded_csv = st.file_uploader("Upload Schedule (.csv)", type=["csv"])

if uploaded_zip and uploaded_csv:
    try:
        df = pd.read_csv(uploaded_csv)
        st.markdown("---")
        
        # PREVIEW ENGINE
        st.subheader("🔍 Preview Engine")
        preview_row = st.selectbox("Select a row to preview", df.index, 
                                   format_func=lambda x: f"{df.iloc[x].get('City', 'Unknown')} ({df.iloc[x].get('Filename', 'No File')})")
        
        if st.button("GENERATE PREVIEW"):
            base_dir = tempfile.mkdtemp()
            try:
                # Initialization
                v_dir = os.path.join(base_dir, "videos")
                os.makedirs(v_dir, exist_ok=True)
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    z.extractall(v_dir)
                
                f_path = None
                if uploaded_font:
                    f_path = os.path.join(base_dir, "custom.ttf")
                    with open(f_path, "wb") as f: f.write(uploaded_font.read())

                with st.spinner("Rendering preview..."):
                    out_p = os.path.join(base_dir, "preview.mp4")
                    if render_video(df.iloc[preview_row], v_dir, f_path, out_p):
                        st.video(out_p)
            finally:
                shutil.rmtree(base_dir)

        # BATCH ENGINE
        st.subheader("🚀 Batch Processing")
        if st.button("RUN FULL BATCH"):
            base_dir = tempfile.mkdtemp()
            try:
                # Initialization
                v_dir = os.path.join(base_dir, "videos")
                o_dir = os.path.join(base_dir, "output")
                os.makedirs(v_dir, exist_ok=True)
                os.makedirs(o_dir, exist_ok=True)

                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    z.extractall(v_dir)

                f_path = None
                if uploaded_font:
                    f_path = os.path.join(base_dir, "custom.ttf")
                    with open(f_path, "wb") as f: f.write(uploaded_font.read())

                processed = []
                prog = st.progress(0)
                for i, row in df.iterrows():
                    out_name = f"Promo_{str(row.get('City','')).replace(' ', '_')}_{row.get('Filename','')}"
                    out_p = os.path.join(o_dir, out_name)
                    if render_video(row, v_dir, f_path, out_p):
                        processed.append(out_p)
                    prog.progress((i + 1) / len(df))

                if processed:
                    zip_path = os.path.join(base_dir, "Results.zip")
                    with zipfile.ZipFile(zip_path, 'w') as z:
                        for f in processed: z.write(f, os.path.basename(f))
                    st.success(f"Generated {len(processed)} videos!")
                    with open(zip_path, "rb") as f:
                        st.download_button("DOWNLOAD ZIP", f, "Tour_Assets.zip")
            finally:
                shutil.rmtree(base_dir)
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
