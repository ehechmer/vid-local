import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
import random
import time
import subprocess
import re
import io
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

# --- COMPATIBILITY PATCH ---
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- 1. CONFIG & UTILS ---
APP_NAME = "L&K Localizer - Live Editor"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_col(df, options):
    for opt in options:
        if opt in df.columns: return opt
    return None

def get_duration_ffprobe(filepath):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        return float(subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip())
    except: return None

def find_video_path(root_dir, filename):
    direct = os.path.join(root_dir, filename)
    if os.path.exists(direct):
        return direct
    for root, _dirs, files in os.walk(root_dir):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return direct

# --- 2. SESSION STATE MANAGEMENT ---
if 'preview_img_cache' not in st.session_state:
    st.session_state.preview_img_cache = None
if 'current_preview_file' not in st.session_state:
    st.session_state.current_preview_file = None
if 'current_frame_time' not in st.session_state:
    st.session_state.current_frame_time = 0.0

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="wide")

# --- 3. UI STYLING ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700&family=Source+Sans+3:wght@400;600&display=swap');
    .stApp {{
        transition: all 0.3s ease;
        background: radial-gradient(1200px 600px at 10% 0%, #f2f7fb 0%, #ffffff 50%, #eef4f8 100%);
    }}
    h1, h3 {{
        text-align: center;
        text-transform: uppercase;
        font-family: 'Montserrat', sans-serif;
        letter-spacing: 0.08em;
    }}
    .stMarkdown, .stText, .stTextInput, .stSelectbox, .stDataFrame {{
        font-family: 'Source Sans 3', sans-serif;
    }}
    .stButton>button {{
        border: 2px solid {PRIMARY_COLOR};
        color: {PRIMARY_COLOR};
        font-weight: 700;
        width: 100%;
        letter-spacing: 0.04em;
        background: white;
        border-radius: 10px;
        padding: 0.5rem 1rem;
    }}
    .block-card {{
        background: #ffffff;
        border: 1px solid #e6eef5;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
    }}
    
    div[data-testid="stImage"] {{
        display: flex;
        justify-content: center;
        align-items: flex-start;
    }}
    div[data-testid="stImage"] img {{
        max-width: 300px !important;
        max-height: 80vh !important;
        object-fit: contain;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🎨 DESIGN STUDIO")
    
    st.subheader("1. Layout & Motion")
    motion_profile = st.selectbox("Animation Style:", 
                                  ["Static", "Cinematic Lift", "Zoom Pop", "Ghost Drift", "Shake", "Split Convergence"])
    
    st.markdown("---")
    st.subheader("2. Typography")
    v_text_color = st.color_picker("Text Color", "#FFFFFF")
    v_stroke_color = st.color_picker("Outline Color", "#000000")
    
    c1, c2 = st.columns(2)
    with c1:
        v_size_main = st.slider("Title Size", 40, 400, 150)
        v_stroke_width = st.slider("Outline", 0, 20, 4)
    with c2:
        v_size_small = st.slider("Body Size", 20, 300, 120)
        v_shadow_offset = st.slider("Shadow", 0, 20, 4)

    st.markdown("---")
    st.subheader("3. Positioning (Offsets)")
    pos_x = st.slider("↔️ Horizontal Offset", -500, 500, 0, step=10, help="Negative = Left, Positive = Right")
    pos_y = st.slider("↕️ Vertical Offset", -500, 500, 0, step=10, help="Negative = Up, Positive = Down")

def update_color_globals():
    global TEXT_RGB, STROKE_RGB
    TEXT_RGB = hex_to_rgb(v_text_color)
    STROKE_RGB = hex_to_rgb(v_stroke_color)

update_color_globals()

# --- 5. CORE LOGIC ---
def get_scaled_font(text, font_path, max_size, target_width, target_height, stroke_w=0, spacing=-12):
    size = max_size
    try:
        font = ImageFont.truetype(font_path, int(size)) if font_path else ImageFont.load_default()
    except:
        return ImageFont.load_default(), size

    dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    for s in range(int(max_size), 20, -2):
        test_font = ImageFont.truetype(font_path, s) if font_path else font
        bbox = dummy.textbbox((0, 0), text, font=test_font, spacing=spacing, stroke_width=stroke_w, align='center')
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= target_width and text_h <= target_height:
            return test_font, s
    return font, size

def slugify(text):
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")

def build_output_name(row, col_map, prefix, suffix, sep, slugify_city, use_filename_stem):
    city = str(row.get(col_map['city'], '')).strip()
    filename = str(row.get(col_map['filename'], '')).strip()
    filename_stem, ext = os.path.splitext(filename)
    city_part = slugify(city) if slugify_city else city.replace(" ", "_")
    base_parts = []
    if prefix:
        base_parts.append(prefix)
    if city_part:
        base_parts.append(city_part)
    if use_filename_stem and filename_stem:
        base_parts.append(filename_stem)
    base = sep.join([p for p in base_parts if p])
    if suffix:
        base = f"{base}{sep}{suffix}" if base else suffix
    return f"{base}.mp4" if base else f"output_{filename_stem or 'video'}.mp4"

def validate_rows(df, col_map):
    errors = []
    if not col_map.get('filename'):
        errors.append("Missing a column mapped to filename.")
    if not col_map.get('city'):
        errors.append("Missing a column mapped to city.")
    if errors:
        return errors
    for i, row in df.iterrows():
        fname = str(row.get(col_map['filename'], '')).strip()
        city = str(row.get(col_map['city'], '')).strip()
        if not fname:
            errors.append(f"Row {i}: missing filename")
        if not city:
            errors.append(f"Row {i}: missing city")
    return errors

def draw_text_on_image(base_img, text, font_path, font_size, color, stroke, stroke_w, shadow_off, offset_x=0, offset_y=0):
    img = base_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    W, H = img.size
    
    target_w = W * 0.85
    target_h = H * 0.85
    font, final_size = get_scaled_font(
        text,
        font_path,
        font_size,
        target_w,
        target_h,
        stroke_w=stroke_w,
        spacing=-12,
    )
    
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_w, spacing=-12)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = ((W - text_w) / 2 - bbox[0]) + offset_x
    y = ((H - text_h) / 2 - bbox[1]) + offset_y
    
    if shadow_off > 0:
        draw.text((x + shadow_off, y + shadow_off), text, font=font, fill=stroke, align='center', spacing=-12)
    
    draw.text((x, y), text, font=font, fill=color, align='center', stroke_width=stroke_w, stroke_fill=stroke, spacing=-12)
    return img

def create_split_convergence(text, font_path, font_size, video_w, video_h, duration, start_time, offset_x=0, offset_y=0):
    lines = text.split('\n')
    clips = []
    target_w = video_w * 0.85
    target_h = video_h * 0.85
    font, final_size = get_scaled_font(
        text,
        font_path,
        font_size,
        target_w,
        target_h,
        stroke_w=v_stroke_width,
        spacing=-12,
    )
    
    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    line_heights = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font, stroke_width=v_stroke_width)
        line_heights.append((bbox[3] - bbox[1]) + 20)
    
    total_h = sum(line_heights)
    
    start_y_cursor = ((video_h / 2) - (total_h / 2)) + offset_y
    
    for i, line in enumerate(lines):
        dummy_img = Image.new('RGBA', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), line, font=font, align='center', stroke_width=v_stroke_width)
        w, h = int((bbox[2]-bbox[0])+80), int((bbox[3]-bbox[1])+80)
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pos = (int(40-bbox[0]), int(40-bbox[1]))
        if v_shadow_offset > 0:
            draw.text((pos[0]+v_shadow_offset, pos[1]+v_shadow_offset), line, font=font, fill=STROKE_RGB, align='center')
        draw.text(pos, line, font=font, fill=TEXT_RGB, align='center', stroke_width=v_stroke_width, stroke_fill=STROKE_RGB)
        
        line_clip = ImageClip(np.array(img)).set_duration(duration).set_start(start_time)
        
        final_y = start_y_cursor
        start_y_cursor += line_heights[i]
        
        final_x = ((video_w / 2) - (w / 2)) + offset_x
        start_x = -w if i % 2 == 0 else video_w
        
        def pos_func(t, sx=start_x, fx=final_x, fy=final_y, st=start_time):
            rel_t = t - st
            if rel_t < 0: return (sx, fy)
            progress = min(1, rel_t / 0.5)
            ease = 1 - (1 - progress) ** 4
            curr_x = sx + (fx - sx) * ease
            return (curr_x, fy)
            
        clips.append(line_clip.set_position(pos_func))
    return CompositeVideoClip(clips, size=(video_w, video_h)).set_duration(duration).set_start(start_time)

# --- 6. RENDER FUNCTION (FIXED) ---
def render_video(row, videos_dir, font_path, output_path, col_map):
    filename = str(row.get(col_map['filename'])).strip()
    video_full_path = find_video_path(videos_dir, filename)
    
    clip = None # <--- FIX: Initialize clip before try block
    
    try:
        clip = VideoFileClip(video_full_path)
        if not clip.duration: clip.duration = get_duration_ffprobe(video_full_path) or 10.0
        
        w, h = clip.size
        dur = clip.duration
        t1_dur, t2_start = dur * 0.25, dur * 0.25
        t2_dur, t3_start = dur * 0.55, dur * 0.80
        t3_dur = dur * 0.20

        # Intro
        txt1_img = draw_text_on_image(Image.new("RGBA", (w,h)), "LAWRENCE\nWITH JACOB JEFFRIES", font_path, v_size_main, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset, pos_x, pos_y)
        txt1 = ImageClip(np.array(txt1_img)).set_duration(t1_dur).set_position('center').crossfadeout(0.2)
        
        # Middle
        city = str(row.get(col_map['city'], 'Unknown')).upper()
        date_val = row.get(col_map.get('date', 'Date'), '')
        venue_val = row.get(col_map.get('venue', 'Venue'), '')
        ticket_val = row.get(col_map.get('ticket', 'Ticket_Link'), '')
        content2 = f"{date_val}\n{city}\n{venue_val}".upper()
        if motion_profile == "Split Convergence":
            txt2 = create_split_convergence(content2, font_path, v_size_small, w, h, t2_dur, t2_start, pos_x, pos_y)
        else:
            base_img = Image.new("RGBA", (w,h))
            overlay = draw_text_on_image(base_img, content2, font_path, v_size_small, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset, pos_x, pos_y)
            txt2 = ImageClip(np.array(overlay)).set_duration(t2_dur).set_position('center').set_start(t2_start).crossfadein(0.2)

        # Outro
        content3 = f"TICKETS ON SALE NOW\n{ticket_val}".upper()
        if motion_profile == "Split Convergence":
            txt3 = create_split_convergence(content3, font_path, v_size_small, w, h, t3_dur, t3_start, pos_x, pos_y)
        else:
            overlay3 = draw_text_on_image(Image.new("RGBA", (w,h)), content3, font_path, v_size_small, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset, pos_x, pos_y)
            txt3 = ImageClip(np.array(overlay3)).set_duration(t3_dur).set_position('center').set_start(t3_start)

        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', verbose=False, logger=None)
        clip.close()
        return True, "Success"
    except Exception as e:
        if clip: clip.close()
        return False, str(e)

# --- 7. MAIN APP LAYOUT ---
st.title(APP_NAME)
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

col_files, col_preview = st.columns([1, 1])

with col_files:
    uploaded_zip = st.file_uploader("1. Video Zip", type=["zip"])
    uploaded_csv = st.file_uploader("2. Tour CSV", type=["csv"])
    uploaded_font = st.file_uploader("3. Font (.ttf)", type=["ttf"])

if uploaded_zip and uploaded_csv:
    df = pd.read_csv(uploaded_csv)
    col_map = {
        'filename': get_col(df, ['Filename', 'File Name', 'Video', 'filename']),
        'city': get_col(df, ['City', 'Location', 'city'])
    }
    
    if not col_map['filename']:
        st.error("🚨 CSV Error: Missing 'Filename' or 'City' column.")
    else:
        # --- PREVIEW SETUP ---
        with col_files:
            st.markdown("---")
            st.subheader("📍 Select Data")
            preview_idx = st.selectbox("Choose row:", df.index, format_func=lambda x: f"{df.iloc[x].get(col_map['city'], 'Unknown')}")
            
            row = df.iloc[preview_idx]
            city_name = str(row.get(col_map['city'], 'Unknown')).upper()
            video_file = str(row.get(col_map['filename'])).strip()
            
            # Temporary Dir Management
            if 'temp_dir' not in st.session_state:
                st.session_state.temp_dir = tempfile.mkdtemp()
            
            # Extract video if needed
            video_path = os.path.join(st.session_state.temp_dir, video_file)
            if not os.path.exists(video_path):
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    try:
                        for name in z.namelist():
                            if os.path.basename(name) == video_file:
                                source = z.open(name)
                                target = open(video_path, "wb")
                                with source, target:
                                    shutil.copyfileobj(source, target)
                                break
                    except:
                        st.error(f"Could not find {video_file} in zip.")
            
            # Update Font
            font_path = os.path.join(st.session_state.temp_dir, "custom_font.ttf")
            if uploaded_font:
                with open(font_path, "wb") as f: f.write(uploaded_font.getvalue())
            else: font_path = None

        with col_preview:
            st.subheader("👁️ LIVE EDITOR")
            
            preview_layer = st.radio("Layer:", ["Intro (Lawrence)", "Middle (City/Venue)", "Outro (Tickets)"], horizontal=True, index=1)
            scrub_time = st.slider("Scrub Video Frame (Sec)", 0.0, 5.0, 0.5, step=0.1)

            # 1. Cache/Refresh the background frame
            frame_cache_key = f"{video_file}_{scrub_time}"
            if st.session_state.get('last_frame_key') != frame_cache_key and os.path.exists(video_path):
                with st.spinner(f"Loading frame..."):
                    try:
                        clip = VideoFileClip(video_path)
                        actual_t = min(scrub_time, clip.duration - 0.1) if clip.duration else scrub_time
                        st.session_state.preview_img_cache = Image.fromarray(clip.get_frame(actual_t))
                        st.session_state.last_frame_key = frame_cache_key
                        clip.close()
                    except:
                        st.error("Failed to load video frame.")

            # 2. Real-time composite
            if st.session_state.preview_img_cache:
                if "Intro" in preview_layer:
                    p_text = "LAWRENCE\nWITH JACOB JEFFRIES"
                    p_size = v_size_main
                elif "Middle" in preview_layer:
                    p_text = f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper()
                    p_size = v_size_small
                else: # Outro
                    p_text = f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper()
                    p_size = v_size_small
                
                final_preview = draw_text_on_image(
                    st.session_state.preview_img_cache, 
                    p_text, 
                    font_path, 
                    p_size, 
                    TEXT_RGB, 
                    STROKE_RGB, 
                    v_stroke_width, 
                    v_shadow_offset,
                    pos_x,
                    pos_y
                )
                
                st.image(final_preview, caption=f"Previewing: {preview_layer}", width=300)
            else:
                st.info("Upload files to start.")

        # --- BATCH RENDER SECTION ---
        st.markdown("---")
        st.subheader("🚀 BATCH PROCESSING")
        if st.button("RENDER ALL VIDEOS"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            output_dir = os.path.join(st.session_state.temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            results = []
            files_to_zip = []
            
            with zipfile.ZipFile(uploaded_zip, 'r') as z:
                z.extractall(st.session_state.temp_dir)

            total = len(df)
            for i, r in df.iterrows():
                c_name = str(r.get(col_map['city'])).replace(" ", "_")
                fname = str(r.get(col_map['filename']))
                out_name = f"Promo_{c_name}_{fname}"
                out_path = os.path.join(output_dir, out_name)
                
                status_text.text(f"Rendering {i+1}/{total}: {c_name}...")
                success, msg = render_video(r, st.session_state.temp_dir, font_path, out_path, col_map)
                
                if success: files_to_zip.append(out_path)
                results.append(f"{c_name}: {'✅' if success else '❌ ' + msg}")
                progress_bar.progress((i + 1) / total)
            
            st.success("Batch Complete!")
            st.expander("View Logs").write(results)
            
            if files_to_zip:
                zip_out = os.path.join(st.session_state.temp_dir, "Final_Assets.zip")
                with zipfile.ZipFile(zip_out, 'w') as z:
                    for f in files_to_zip: z.write(f, os.path.basename(f))
                with open(zip_out, "rb") as f:
                    st.download_button("DOWNLOAD ZIP", f, "Tour_Assets.zip")
