import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

#---1. BRANDING CONFIGURATION [cite: 22-24, 25-27]
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"    # Brand Blue
BACKGROUND_COLOR = "#0A1A1E" # Brand Charcoal
TEXT_COLOR = "#DCE4EA"       # Brand Light Grey

#---2. PAGE SETUP [cite: 29]
st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

#---3. CUSTOM CSS [cite: 31-40]
st.markdown(f"""
<style>
    .stApp {{ background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; font-family: 'Helvetica Neue', sans-serif; }}
    h1 {{ color: {TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; font-size: 40px; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; letter-spacing: 2px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 15px; width: 100%; font-weight: bold; text-transform: uppercase; transition: 0.3s; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
    .stFileUploader label {{ color: {PRIMARY_COLOR}; font-weight: bold; }}
    .stSuccess {{ background-color: rgba(79, 189, 219, 0.2); border-left: 5px solid {PRIMARY_COLOR}; }}
</style>
""", unsafe_allow_html=True)

#---4. TEXT ENGINE (PILLOW) [cite: 42-63]
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

#---5. BATCH LOGIC WITH DYNAMIC MOVEMENT [cite: 65, 82-86, 104-109]
def process_batch(df, videos_dir, font_path, output_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_files = len(df)

    for i, row in df.iterrows():
        filename = row.get('Filename', None)
        video_full_path = os.path.join(videos_dir, filename) if filename else ""

        if not filename or not os.path.exists(video_full_path):
            st.warning(f"SKIPPING: File '{filename}' not found for {row.get('City', 'Unknown')}")
            continue

        city_name = str(row['City']).upper()
        status_text.markdown(f"**PROCESSING ({i+1}/{total_files}):** {city_name}")

        clip = VideoFileClip(video_full_path)
        w, h = clip.size
        duration = clip.duration

        # Format-Aware Scaling: Adjust for Square vs Vertical
        scale = 1.0 if (w / h) < 0.7 else 0.75

        # Dynamic Timing Percentages [cite: 3, 4]
        t1_start, t1_end = 0, duration * 0.20
        t2_start, t2_end = t1_end, duration * 0.85
        t3_start, t3_end = t2_end, duration

        # LAYER 1: Band Name (Static Center) [cite: 95, 96]
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(80 * scale), 'white')
        txt1 = txt1.set_position(('center', 'center')).set_start(t1_start).set_duration(t1_end - t1_start).crossfadeout(0.3)

        # LAYER 2: Date & City (Slide Up Animation) [cite: 98, 100]
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}".upper()
        txt2 = create_pil_text_clip(content2, font_path, int(70 * scale), 'white')
        txt2 = txt2.set_position(lambda t: ('center', (h/2 + 50) - (min(1, t/0.5) * 50)))
        txt2 = txt2.set_start(t2_start).set_duration(t2_end - t2_start).crossfadein(0.3)

        # LAYER 3: Link [cite: 102, 103]
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}".upper()
        txt3 = create_pil_text_clip(content3, font_path, int(70 * scale), 'white')
        txt3 = txt3.set_position(('center', 'center')).set_start(t3_start).set_duration(t3_end - t3_start).crossfadein(0.2)

        # Render [cite: 105, 107]
        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        output_filename = f"Promo_{city_name.replace(' ', '_')}_{filename}"
        output_path = os.path.join(output_dir, output_filename)
        
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        
        generated_paths.append(output_path)
        progress_bar.progress((i + 1) / total_files)
        clip.close()

    return generated_paths

#---6. FRONT END [cite: 110-120]
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
    if uploaded_csv:
        st.info("Ensure CSV has column: 'Filename' [cite: 121]")

# Button and Logic Block [cite: 122-125]
if uploaded_zip and uploaded_csv:
    st.markdown("---")
    if st.button("INITIALIZE BATCH ENGINE"):
        base_dir = tempfile.mkdtemp()
        videos_dir = os.path.join(base_dir, "videos")
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(videos_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True) [cite: 127-131]

        # 1. Unzip [cite: 133]
        with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
            zip_ref.extractall(videos_dir)

        # 2. Font [cite: 137, 138]
        font_path = None
        if uploaded_font:
            font_path = os.path.join(base_dir, "custom.ttf")
            with open(font_path, "wb") as f: 
                f.write(uploaded_font.read())

        # 3. Process [cite: 141, 142]
        try:
            df = pd.read_csv(uploaded_csv)
            processed_files = process_batch(df, videos_dir, font_path, output_dir)
            
            if processed_files:
                # 4. Zip Results [cite: 146, 147]
                zip_path = os.path.join(base_dir, f"{APP_NAME}_Results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in processed_files: 
                        zipf.write(f, os.path.basename(f))
                
                st.balloons() [cite: 150]
                st.success(f"COMPLETE: {len(processed_files)} Videos Generated") [cite: 151]
                with open(zip_path, "rb") as f:
                    st.download_button("DOWNLOAD ALL VIDEOS", f, "Tour_Assets.zip", "application/zip") [cite: 153]
        except Exception as e:
            st.error(f"System Error: {str(e)}") [cite: 155]
        finally:
            shutil.rmtree(base_dir) [cite: 157]
