import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
import random
import time
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

#---1. BRANDING & STYLE CONFIGURATION
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"

with st.sidebar:
    st.header("🎨 UI & MOTION TUNING")
    ui_mode = st.radio("UI Theme:", ["Dark Mode", "Light Mode"])
    
    st.markdown("---")
    st.subheader("🎬 Motion Settings")
    motion_profile = st.selectbox("Choose Animation Style:", 
                                  ["Static", "Cinematic Lift", "Zoom Pop", "Ghost Drift", "Shake"])
    
    st.markdown("---")
    st.subheader("🎥 Video Text Settings")
    v_text_color = st.color_picker("Text Color", "#FFFFFF")
    v_stroke_color = st.color_picker("Outline Color", "#000000")
    v_stroke_width = st.slider("Outline Thickness", 1, 15, 4)
    v_size_main = st.slider("Main Title Size", 40, 250, 150)
    v_size_small = st.slider("Small Print Size", 20, 200, 120)
    
    st.markdown("---")
    if st.button("♻️ RESET EVERYTHING"):
        st.rerun()

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

TEXT_RGB = hex_to_rgb(v_text_color)
STROKE_RGB = hex_to_rgb(v_stroke_color)

# Forced High-Contrast UI Colors for Dark Mode visibility
BG_COLOR = "#0A1A1E" if ui_mode == "Dark Mode" else "#F0F2F6"
UI_LABEL_COLOR = "#FFFFFF" if ui_mode == "Dark Mode" else "#000000"

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

#---2. HIGH-CONTRAST UI STYLING
st.markdown(f"""
<style>
    .stApp {{ background-color: {BG_COLOR}; color: {UI_LABEL_COLOR}; }}
    
    /* Force ALL labels to be Pure White in Dark Mode */
    label, .stMarkdown p, .stFileUploader label p {{ 
        color: {UI_LABEL_COLOR} !important; 
        font-weight: 800 !important; 
        font-size: 1.1rem !important;
        opacity: 1 !important;
    }}
    
    .stFileUploader section {{ 
        border: 2px dashed {PRIMARY_COLOR} !important; 
        background-color: rgba(255, 255, 255, 0.05) !important; 
    }}
    
    h1, h3 {{ color: {UI_LABEL_COLOR}; text-align: center; text-transform: uppercase; }}
    h4 {{ color: {PRIMARY_COLOR} !important; border-bottom: 2px solid {PRIMARY_COLOR}; }}
    
    .stButton>button {{ border: 2px solid {PRIMARY_COLOR}; color: {PRIMARY_COLOR}; font-weight: bold; width: 100%; }}
</style>
""", unsafe_allow_html=True)

#---3. HELPER: COLUMN FINDER
def get_col(df, possible_names):
    for name in possible_names:
        for col in df.columns:
            if col.strip().lower() == name.lower(): return col
    return None

#---4. TYPOGRAPHY ENGINE
def create_pil_text_clip(text, font_path, font_size, color=TEXT_RGB, stroke_width=v_stroke_width, stroke_color=STROKE_RGB):
    try:
        font = ImageFont.truetype(font_path, int(font_size)) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width, spacing=-10)
    w, h = int((bbox[2]-bbox[0])+80), int((bbox[3]-bbox[1])+80)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pos = (int(40-bbox[0]), int(40-bbox[1]))
    draw.text(pos, text, font=font, fill=color, align='center', stroke_width=stroke_width, stroke_fill=stroke_color, spacing=-10)
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

    try:
        # Stabilized duration loading
        clip = VideoFileClip(video_full_path)
        if clip.duration is None or clip.duration == 0:
            time.sleep(0.5) # Brief wait for OS file lock
            clip = VideoFileClip(video_full_path)
            
        w, h = clip.size
        dur = clip.duration
        scale = 1.0 if (w / h) < 0.7 else 0.75
        
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(v_size_main*scale))
        txt1 = txt1.set_position('center').set_start(0).set_duration(dur*0.25).crossfadeout(0.2)
        
        city_name = str(row.get(city_col, 'Unknown')).upper()
        content2 = f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper()
        txt2_base = create_pil_text_clip(content2, font_path, int(v_size_small*scale))
        txt2 = apply_motion(txt2_base, motion_profile, w, h, dur, dur*0.25).set_start(dur*0.25).set_duration(dur*0.55)
        
        txt3_base = create_pil_text_clip(f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper(), font_path, int(v_size_small*scale))
        txt3 = apply_motion(txt3_base, motion_profile, w, h, dur, dur*0.80).set_start(dur*0.80).set_duration(dur*0.20)
        
        CompositeVideoClip([clip, txt1, txt2, txt3]).write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        clip.close()
        return True, "Success"
    except Exception as e: return False, str(e)

#---5. UI LAYOUT
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
    col_map = {'filename': get_col(df, ['Filename', 'File Name', 'Video']), 'city': get_col(df, ['City', 'Location'])}
    
    if not col_map['filename']:
        st.error("🚨 Check CSV headers!")
    else:
        st.markdown("---")
        st.subheader(f"🔍 PREVIEW ENGINE")
        preview_row = st.selectbox("Pick city to test graphics:", df.index, format_func=lambda x: f"{df.iloc[x].get(col_map['city'], 'Unknown')}")
        
        if st.button("RENDER PREVIEW WITH SETTINGS"):
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
