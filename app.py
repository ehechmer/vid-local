import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
import random
import time
import subprocess  # <--- Added for direct FFprobe calls
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

# --- COMPATIBILITY PATCH FOR PILLOW 10+ ---
# Fixes 'AttributeError: module PIL.Image has no attribute ANTIALIAS'
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- 1. BRANDING & STYLE CONFIGURATION ---
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"

with st.sidebar:
    st.header("🎨 UI & MOTION TUNING")
    ui_mode = st.radio("UI Theme:", ["Light Mode", "Dark Mode"], index=0)
    
    st.markdown("---")
    st.subheader("🎬 Motion Settings")
    motion_profile = st.selectbox("Choose Animation Style:", 
                                  ["Static", "Cinematic Lift", "Zoom Pop", "Ghost Drift", "Shake"])
    
    st.markdown("---")
    st.subheader("🎥 Video Text Settings")
    v_text_color = st.color_picker("Text Color", "#FFFFFF")
    v_stroke_color = st.color_picker("Outline Color", "#000000")
    v_stroke_width = st.slider("Outline Thickness", 1, 15, 4)
    v_shadow_offset = st.slider("Drop Shadow Offset", 0, 10, 4)
    v_size_main = st.slider("Max Title Size", 40, 300, 150)
    v_size_small = st.slider("Max Small Print Size", 20, 250, 120)
    
    st.markdown("---")
    if st.button("♻️ RESET EVERYTHING"):
        st.rerun()

# --- 2. UTILITY FUNCTIONS ---
def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_col(df, options):
    """Detects existing columns from a list of potential names."""
    for opt in options:
        if opt in df.columns:
            return opt
    return None

def get_duration_ffprobe(filepath):
    """Force-reads video duration using system-level ffprobe, bypassing MoviePy errors."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ]
        # Run command and decode output
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        return float(output)
    except Exception:
        return None

TEXT_RGB = hex_to_rgb(v_text_color)
STROKE_RGB = hex_to_rgb(v_stroke_color)

# Theme Logic
if ui_mode == "Light Mode":
    BG_COLOR = "#F0F2F6"
    UI_LABEL_COLOR = "#000000"
    BOX_BG = "rgba(0, 0, 0, 0.05)"
else:
    BG_COLOR = "#0A1A1E"
    UI_LABEL_COLOR = "#FFFFFF"
    BOX_BG = "rgba(255, 255, 255, 0.05)"

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

st.markdown(f"""
<style>
    .stApp {{ background-color: {BG_COLOR}; color: {UI_LABEL_COLOR}; transition: all 0.3s ease; }}
    label, .stMarkdown p, .stFileUploader label p, div[data-testid="stWidgetLabel"] p {{ 
        color: {UI_LABEL_COLOR} !important; 
        font-weight: 800 !important; 
        font-size: 1.1rem !important;
    }}
    .stFileUploader section {{ 
        border: 2px dashed {PRIMARY_COLOR} !important; 
        background-color: {BOX_BG} !important; 
        border-radius: 10px;
    }}
    h1, h3 {{ color: {UI_LABEL_COLOR} !important; text-align: center; text-transform: uppercase; }}
    h4 {{ color: {PRIMARY_COLOR} !important; border-bottom: 2px solid {PRIMARY_COLOR}; }}
    .stButton>button {{ border: 2px solid {PRIMARY_COLOR}; color: {PRIMARY_COLOR}; font-weight: bold; width: 100%; }}
</style>
""", unsafe_allow_html=True)

# --- 3. RENDERING ENGINE ---
def get_scaled_font(text, font_path, max_size, target_width):
    size = max_size
    try:
        font = ImageFont.truetype(font_path, int(size)) if font_path else ImageFont.load_default()
    except:
        return ImageFont.load_default(), size

    for s in range(int(max_size), 20, -5):
        test_font = ImageFont.truetype(font_path, s) if font_path else font
        dummy_img = Image.new('RGBA', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), text, font=test_font, spacing=-12)
        if (bbox[2] - bbox[0]) < target_width:
            return test_font, s
    return font, size

def create_pil_text_clip(text, font_path, font_size, video_w, color=TEXT_RGB, stroke_width=v_stroke_width, stroke_color=STROKE_RGB):
    target_w = video_w * 0.85 
    font, final_size = get_scaled_font(text, font_path, font_size, target_w)
    
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width, spacing=-12)
    w, h = int((bbox[2]-bbox[0])+100), int((bbox[3]-bbox[1])+100)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pos = (int(50-bbox[0]), int(50-bbox[1]))
    
    if v_shadow_offset > 0:
        draw.text((pos[0]+v_shadow_offset, pos[1]+v_shadow_offset), text, font=font, fill=stroke_color, align='center', spacing=-12)
    
    draw.text(pos, text, font=font, fill=color, align='center', stroke_width=stroke_width, stroke_fill=stroke_color, spacing=-12)
    return ImageClip(np.array(img))

def apply_motion(clip, style, w, h, duration, start_time):
    if style == "Cinematic Lift":
        return clip.set_position(lambda t: ('center', (h/2 + 40) - (min(1, (t-start_time)/0.5) * 40))).crossfadein(0.2)
    elif style == "Zoom Pop":
        return clip.set_position('center').resize(lambda t: 1.25 - 0.25 * min(1, (t-start_time)/0.35)).crossfadein(0.15)
    elif style == "Ghost Drift":
        return clip.set_position(lambda t: ((w/2 - clip.w/2) + ((t-start_time) * 18), 'center')).crossfadein(0.4)
    elif style == "Shake":
        return clip.set_position(lambda t: ('center' if (t-start_time) < 0 else ('center', (h/2 - clip.h/2) + random.uniform(-4, 4)))).crossfadein(0.1)
    else:
        return clip.set_position('center')

def render_video(row, videos_dir, font_path, output_path, col_map):
    fname_col, city_col = col_map.get('filename'), col_map.get('city')
    filename = str(row.get(fname_col, '')).strip()
    video_full_path = os.path.join(videos_dir, filename)
    
    if not filename or not os.path.exists(video_full_path): 
        return False, f"File '{filename}' not found"

    clip = None
    try:
        # 1. Initialize Clip
        clip = VideoFileClip(video_full_path)
        
        # 2. ROBUST DURATION CHECK (The "Safety Net")
        if not clip.duration or clip.duration == 0:
            # Attempt 1: Internal reader
            if hasattr(clip, 'reader') and clip.reader.duration:
                clip.duration = clip.reader.duration
            
            # Attempt 2: External FFprobe (Bypasses MoviePy)
            if not clip.duration:
                clip.duration = get_duration_ffprobe(video_full_path)
            
            # Attempt 3: Hard Fallback (Prevents Crash)
            if not clip.duration:
                print(f"WARNING: Could not detect duration for {filename}. Defaulting to 10s.")
                clip.duration = 10.0  # Safe default to ensure render completes
        
        # Now 'dur' is guaranteed to be a float
        w, h = clip.size
        dur = clip.duration
        
        # 3. Create Overlays
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, v_size_main, w).set_position('center').set_start(0).set_duration(dur*0.25).crossfadeout(0.2)
        
        city_name = str(row.get(city_col, 'Unknown')).upper()
        content2 = f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper()
        txt2 = apply_motion(create_pil_text_clip(content2, font_path, v_size_small, w), motion_profile, w, h, dur, dur*0.25).set_start(dur*0.25).set_duration(dur*0.55)
        
        txt3 = apply_motion(create_pil_text_clip(f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper(), font_path, v_size_small, w), motion_profile, w, h, dur, dur*0.80).set_start(dur*0.80).set_duration(dur*0.20)
        
        # 4. Render
        final_video = CompositeVideoClip([clip, txt1, txt2, txt3])
        final_video.write_videofile(
            output_path, 
            codec='libx264', 
            audio_codec='aac', 
            fps=24, 
            verbose=False, 
            logger=None, 
            preset='ultrafast'
        )
        
        # 5. Cleanup
        clip.close()
        return True, "Success"
        
    except Exception as e:
        if clip:
            try: clip.close() 
            except: pass
        return False, str(e)

# --- 4. UI LAYOUT ---
st.title(APP_NAME)
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    uploaded_zip = st.file_uploader("📁 UPLOAD VIDEO ZIP", type=["zip"])
    uploaded_font = st.file_uploader("🔤 UPLOAD FONT (.TTF)", type=["ttf"])
with c2:
    uploaded_csv = st.file_uploader("📄 UPLOAD TOUR CSV", type=["csv"])

if uploaded_zip and uploaded_csv:
    df = pd.read_csv(uploaded_csv)
    col_map = {
        'filename': get_col(df, ['Filename', 'File Name', 'Video', 'filename']), 
        'city': get_col(df, ['City', 'Location', 'city'])
    }
    
    if not col_map['filename']:
        st.error("🚨 Check CSV headers! Could not find a 'Filename' or 'Video' column.")
    else:
        st.markdown("---")
        st.subheader("🔍 PREVIEW ENGINE")
        preview_row = st.selectbox("Pick city to test graphics:", df.index, format_func=lambda x: f"{df.iloc[x].get(col_map['city'], 'Unknown')}")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("⚡ FAST TEXT PREVIEW"):
                row = df.iloc[preview_row]
                city_name = str(row.get(col_map['city'], 'Unknown')).upper()
                f_p = None
                t1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", f_p, v_size_main, 1080)
                t2 = create_pil_text_clip(f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper(), f_p, v_size_small, 1080)
                t3 = create_pil_text_clip(f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper(), f_p, v_size_small, 1080)
                st.image(t1.img, caption="1. INTRO")
                st.image(t2.img, caption="2. MIDDLE")
                st.image(t3.img, caption="3. OUTRO")
        
        with btn_col2:
            if st.button("🎬 FULL VIDEO PREVIEW"):
                base_dir = tempfile.mkdtemp()
                try:
                    v_dir = os.path.join(base_dir, "v"); os.makedirs(v_dir, exist_ok=True)
                    with zipfile.ZipFile(uploaded_zip, 'r') as z:
                        for member in z.infolist():
                            if not member.is_dir(): member.filename = os.path.basename(member.filename); z.extract(member, v_dir)
                    f_p = os.path.join(base_dir, "f.ttf") if uploaded_font else None
                    if f_p: 
                        with open(f_p, "wb") as f: f.write(uploaded_font.read())
                    with st.spinner("Rendering..."):
                        out = os.path.join(base_dir, "p.mp4")
                        success, msg = render_video(df.iloc[preview_row], v_dir, f_p, out, col_map)
                        if success: st.video(out)
                        else: st.error(msg)
                finally: shutil.rmtree(base_dir)

        st.subheader("🚀 BATCH PROCESSING")
        if st.button("RUN FULL BATCH"):
            base_dir = tempfile.mkdtemp()
            try:
                v_dir, o_dir = os.path.join(base_dir, "v"), os.path.join(base_dir, "o")
                os.makedirs(v_dir, exist_ok=True); os.makedirs(o_dir, exist_ok=True)
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    for m in z.infolist():
                        if not m.is_dir(): m.filename = os.path.basename(m.filename); z.extract(m, v_dir)
                f_p = os.path.join(base_dir, "f.ttf") if uploaded_font else None
                if f_p: 
                    with open(f_p, "wb") as f: f.write(uploaded_font.read())
                processed, log_data, status_container = [], [], st.empty()
                prog = st.progress(0)
                for i, row in df.iterrows():
                    city, orig_fname = str(row.get(col_map['city'], 'Unknown')), str(row.get(col_map['filename'], 'video'))
                    out_path = os.path.join(o_dir, f"Promo_{city.replace(' ', '_')}_{orig_fname}")
                    success, msg = render_video(row, v_dir, f_p, out_path, col_map)
                    log_data.append({"City": city, "Status": "✅" if success else f"❌ {msg}"})
                    status_container.table(log_data)
                    if success: processed.append(out_path)
                    prog.progress((i + 1) / len(df))
                if processed:
                    z_path = os.path.join(base_dir, "Results.zip")
                    with zipfile.ZipFile(z_path, 'w') as z:
                        for f in processed: z.write(f, os.path.basename(f))
                    st.download_button("Download All Videos", open(z_path, "rb"), "Tour_Assets.zip")
            finally: shutil.rmtree(base_dir)
