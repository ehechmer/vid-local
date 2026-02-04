import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

# --- 1. BRANDING CONFIGURATION ---
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY"
PRIMARY_COLOR = "#4FBDDB"  # L&K Blue
BACKGROUND_COLOR = "#0A1A1E"
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
    .stWarning {{ background-color: rgba(255, 255, 0, 0.1); border-left: 5px solid yellow; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. TEXT ENGINE (PILLOW) ---
def create_pil_text_clip(text, font_path, font_size, color, stroke_width=2, stroke_color='black'):
    """Generates transparent text image safely using PIL."""
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
    
    text_width = int(bbox[2] - bbox[0])
    text_height = int(bbox[3] - bbox[1])
    width = int(text_width + 40)
    height = int(text_height + 40)

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    x_pos = int(20 - bbox[0])
    y_pos = int(20 - bbox[1])
    
    draw.text((x_pos, y_pos), text, font=font, fill=color, align='center', 
              stroke_width=stroke_width, stroke_fill=stroke_color)

    return ImageClip(np.array(img))

# --- 5. BATCH LOGIC ---
def process_batch(df, videos_dir, font_path, output_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(df)
    
    for i, row in df.iterrows():
        # 1. Identify which video to use
        # We look for a 'Filename' column in the CSV. If missing, we warn the user.
        filename = row.get('Filename', None)
        
        # If no filename specified, or file not found, skip
        if not filename or not os.path.exists(os.path.join(videos_dir, filename)):
            st.warning(f"⚠️ SKIPPING: Could not find video '{filename}' for {row['City']}")
            continue
            
        video_path = os.path.join(videos_dir, filename)
        city_name = str(row['City']).upper()
        status_text.markdown(f"**PROCESSING ({i+1}/{total_files}):** {city_name} using *{filename}*")
        
        # 2. Load Video & Calculate Dynamic Times
        clip = VideoFileClip(video_path)
        duration = clip.duration
        
        # --- DYNAMIC TIMING LOGIC ---
        # Instead of fixed seconds, we use percentages of the total duration.
        # T1 (Band): 0% to 20%
        # T2 (City): 20% to 80%
        # T3 (Link): 80% to 100%
        
        t1_start = 0
        t1_end = duration * 0.20  # Ends at 20% mark
        
        t2_start = t1_end
        t2_end = duration * 0.85  # Ends at 85% mark
        
        t3_start = t2_end
        t3_end = duration         # Goes to the very end
        
        # 3. Create Text Layers
        
        # LAYER 1: Band Name
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, 80, 'white', stroke_width=3)
        txt1 = txt1.set_position(('center', 'center')).set_start(t1_start).set_duration(t1_end - t1_start)

        # LAYER 2: Date & City
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}"
        txt2 = create_pil_text_clip(content2.upper(), font_path, 70, 'white', stroke_width=3)
        txt2 = txt2.set_position(('center', 'center')).set_start(t2_start).set_duration(t2_end - t2_start)

        # LAYER 3: Link
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}"
        txt3 = create_pil_text_clip(content3.upper(), font_path, 70, 'white', stroke_width=3)
        txt3 = txt3.set_position(('center', 'center')).set_start(t3_start).set_duration(t3_end - t3_start)
        
        # 4. Composite & Render
        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        
        output_filename = f"Promo_{city_name.replace(' ', '')}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        
        generated_paths.append(output_path)
        progress_bar.progress((i + 1) / total_files)
        clip.close()
        
    return generated_paths

# --- 6. FRONT END ---
st.title("VID_LOCAL PRO")
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 1. ASSETS")
        uploaded_zip = st.file_uploader("Upload ZIP of Raw Videos", type=["zip"])
        uploaded_font = st.file_uploader("Upload Font (.ttf) [Optional]", type=["ttf"])
    with col2:
        st.markdown("#### 2. DATA")
        uploaded_csv = st.file_uploader("Upload Schedule (.csv)", type=["csv"])
        if uploaded_csv:
            st.info("Ensure CSV has column: 'Filename'")

if uploaded_zip and uploaded_csv:
    st.markdown("---")
    if st.button("⚡ INITIALIZE BATCH ENGINE"):
        # Create a workspace
        base_dir = tempfile.mkdtemp()
        videos_dir = os.path.join(base_dir, "videos")
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(videos_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Unzip Videos
        with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
            zip_ref.extractall(videos_dir)
            
        # 2. Save Font
        font_path = None
        if uploaded_font:
            font_path = os.path.join(base_dir, "custom.ttf")
            with open(font_path, "wb") as f: f.write(uploaded_font.read())
            
        # 3. Process
        try:
            df = pd.read_csv(uploaded_csv)
            files = process_batch(df, videos_dir, font_path, output_dir)
            
            if not files:
                st.error("No videos were generated. Check your CSV filenames match the ZIP files!")
            else:
                # 4. Zip Results
                zip_path = os.path.join(base_dir, f"{APP_NAME}_Results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in files:
                        zipf.write(file, os.path.basename(file))
                
                st.balloons()
                st.success(f"✅ BATCH COMPLETE: {len(files)} Videos Generated")
                with open(zip_path, "rb") as f:
                    st.download_button("⬇️ DOWNLOAD RESULTS", f, "Tour_Assets.zip", "application/zip")
                    
        except Exception as e:
            st.error(f"System Error: {str(e)}")
        finally:
            # Cleanup temp files to keep server healthy
            shutil.rmtree(base_dir)

