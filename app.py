import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

#---1. BRANDING CONFIGURATION [cite: 22-24]
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"

# COLORS FROM BRAND GUIDELINES
PRIMARY_COLOR = "#4FBDDB"    # Brand Blue
BACKGROUND_COLOR = "#0A1A1E" # Brand Dark Charcoal
TEXT_COLOR = "#DCE4EA"       # Brand Light Grey

#---2. PAGE SETUP [cite: 29]
st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

#---3. CUSTOM CSS [cite: 30-40]
st.markdown(f"""
<style>
    .stApp {{ background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; font-family: 'Helvetica Neue', sans-serif; }}
    h1 {{ color: {TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; font-size: 40px; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; letter-spacing: 2px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 15px; width: 100%; font-weight: bold; text-transform: uppercase; transition: 0.3s; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
    .stFileUploader label {{ color: {PRIMARY_COLOR}; font-weight: bold; }}
    .stSuccess {{ background-color: rgba(79, 189, 219, 0.2); border-left: 5px solid {PRIMARY_COLOR}; }}
    .stInfo {{ background-color: rgba(79, 189, 219, 0.1); }}
</style>
""", unsafe_allow_html=True)

#---4. TEXT ENGINE (PILLOW) [cite: 41-63]
def create_pil_text_clip(text, font_path, font_size, color, stroke_width=3, stroke_color='black'):
    try:
        if font_path:
            font = ImageFont.truetype(font_path, int(font_size))
        else:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(font_size))
    except:
        font = ImageFont.load_default()
    
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width)
    
    width = int((bbox[2] - bbox[0]) + 60)
    height = int((bbox[3] - bbox[1]) + 60)
    
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x_pos = int(30 - bbox[0])
    y_pos = int(30 - bbox[1])
    
    draw.text((x_pos, y_pos), text, font=font, fill=color, align='center', 
              stroke_width=stroke_width, stroke_fill=stroke_color)
    return ImageClip(np.array(img))

#---5. BATCH LOGIC WITH DYNAMIC MOVEMENT [cite: 64-109]
def process_batch(df, videos_dir, font_path, output_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_files = len(df)

    for i, row in df.iterrows():
        filename = row.get('Filename', None)
        if not filename or not os.path.exists(os.path.join(videos_dir, filename)):
            st.warning(f"SKIPPING: Could not find video '{filename}' for {row.get('City', 'Unknown')}") [cite: 74-75]
            continue

        video_path = os.path.join(videos_dir, filename)
        city_name = str(row['City']).upper() [cite: 77]
        status_text.markdown(f"**PROCESSING ({i+1}/{total_files}):** {city_name}") [cite: 78]

        clip = VideoFileClip(video_path)
        w, h = clip.size
        aspect_ratio = w / h
        duration = clip.duration [cite: 81]

        # FONT SCALING: Adjust size based on aspect ratio (Square vs Vertical)
        scale = 1.0 if aspect_ratio < 0.7 else 0.75

        # DYNAMIC TIMING LOGIC (Percentages) [cite: 82-91]
        t1_start, t1_end = 0, duration * 0.20
        t2_start, t2_end = t1_end, duration * 0.85
        t3_start, t3_end = t2_end, duration

        # LAYER 1: Band Name (Static) [cite: 93-96]
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(80 * scale), 'white')
        txt1 = txt1.set_position(('center', 'center')).set_start(t1_start).set_duration(t1_end - t1_start).crossfadeout(0.3)

        # LAYER 2: Date & City (Slide Up Animation) [cite: 97-100]
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}".upper()
        txt2 = create_pil_text_clip(content2, font_path, int(70 * scale), 'white')
        # Movement: Slides from center+50px up to center over 0.5s
        txt2 = txt2.set_position(lambda t: ('center', (h/2 + 50) - (min(1, t/0.5) * 50)))
        txt2 = txt2.set_start(t2_start).set_duration(t2_end - t2_start).crossfadein(0.3)

        # LAYER 3: Link [cite: 101-103]
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}".upper()
        txt3 = create_pil_text_clip(content3, font_path, int(70 * scale), 'white')
        txt3 = txt3.set_position(('center', 'center')).set_start(t3_start).set_duration(t3_end - t3_start).crossfadein(0.2)

        # COMPOSITE & RENDER [cite: 104-107]
        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        output_filename = f"Promo_{city_name.replace(' ', '_')}_{filename}"
        output_path = os.path.join(output_dir, output_filename)
        
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        
        generated_paths.append(output_path) [cite: 108]
        progress_bar.progress((i + 1) / total_files)
        clip.close()

    return generated_paths

#---6. FRONT END [cite: 110-157]
st.title(APP_NAME) [cite: 111]
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True) [cite: 112]

col1, col2 = st.columns(2) [cite: 114]
with col1:
    st.markdown("#### 1. ASSETS") [cite: 116]
    uploaded_zip = st.file_uploader("Upload ZIP of Raw Videos", type=["zip"]) [cite: 117]
    uploaded_font = st.file_uploader("Upload Font (.ttf)", type=["ttf"]) [cite: 118]
with col2:
    st.markdown("#### 2. DATA") [cite: 119]
    uploaded_csv = st.file_uploader("Upload Schedule (.csv)", type=["csv"]) [cite: 120]
    if uploaded_csv:
        st.info("Ensure CSV has column: 'Filename'") [cite: 121]

if uploaded_zip and uploaded_csv: [cite: 122]
    st.markdown("---")
    if st.button("INITIALIZE BATCH ENGINE"): [cite: 124-125]
        base_dir = tempfile.mkdtemp() [cite: 127]
        videos_dir = os.path.join(base_dir, "videos")
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(videos_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True) [cite: 128-131]

        # 1. Unzip [cite: 132-133]
        with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
            zip_ref.extractall(videos_dir)

        # 2. Font Setup [cite: 134-138]
        font_path = None
        if uploaded_font:
            font_path = os.path.join(base_dir, "custom.ttf")
            with open(font_path, "wb") as f: f.write(uploaded_font.read())

        # 3. Process [cite: 139-142]
        try:
            df = pd.read_csv(uploaded_csv) [cite: 141]
            files = process_batch(df, videos_dir, font_path, output_dir) [cite: 142]
            
            if files:
                # 4. Zip Results [cite: 145-149]
                zip_path = os.path.join(base_dir, f"{APP_NAME}_Results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in files: zipf.write(f, os.path.basename(f))
                
                st.balloons() [cite: 150]
                st.success(f"COMPLETE: {len(files)} Videos Generated") [cite: 151]
                with open(zip_path, "rb") as f:
                    st.download_button("DOWNLOAD RESULTS", f, "Tour_Assets.zip", "application/zip") [cite: 152-153]
            else:
                st.error("No videos were generated. Check your CSV filenames!") [cite: 144]
        except Exception as e:
            st.error(f"System Error: {str(e)}") [cite: 154-155]
        finally:
            shutil.rmtree(base_dir) [cite: 157]
