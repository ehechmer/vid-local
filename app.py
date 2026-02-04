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

# --- 2. SESSION STATE MANAGEMENT ---
if 'preview_img_cache' not in st.session_state:
    st.session_state.preview_img_cache = None
if 'current_preview_file' not in st.session_state:
    st.session_state.current_preview_file = None

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="wide") # Switched to WIDE layout for better editor feel

# --- 3. UI STYLING ---
st.markdown(f"""
<style>
    .stApp {{ transition: all 0.3s ease; }}
    h1, h3 {{ text-align: center; text-transform: uppercase; }}
    .stButton>button {{ border: 2px solid {PRIMARY_COLOR}; color: {PRIMARY_COLOR}; font-weight: bold; width: 100%; }}
</style>
""", unsafe_allow_html=True)

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🎨 DESIGN STUDIO")
    
    st.subheader("Layout & Motion")
    motion_profile = st.selectbox("Animation Style:", 
                                  ["Static", "Cinematic Lift", "Zoom Pop", "Ghost Drift", "Shake", "Split Convergence"])
    
    st.markdown("---")
    st.subheader("Typography")
    v_text_color = st.color_picker("Text Color", "#FFFFFF")
    v_stroke_color = st.color_picker("Outline Color", "#000000")
    
    c1, c2 = st.columns(2)
    with c1:
        v_size_main = st.slider("Title Size", 40, 400, 150)
        v_stroke_width = st.slider("Outline", 0, 20, 4)
    with c2:
        v_size_small = st.slider("Body Size", 20, 300, 120)
        v_shadow_offset = st.slider("Shadow", 0, 20, 4)

TEXT_RGB = hex_to_rgb(v_text_color)
STROKE_RGB = hex_to_rgb(v_stroke_color)

# --- 5. CORE LOGIC ---
def get_scaled_font(text, font_path, max_size, target_width):
    lines = text.split('\n')
    longest_line = max(lines, key=len) if lines else text
    size = max_size
    try:
        font = ImageFont.truetype(font_path, int(size)) if font_path else ImageFont.load_default()
    except:
        return ImageFont.load_default(), size

    # Binary searchish optimization could go here, but linear is fast enough for PIL
    for s in range(int(max_size), 20, -5):
        test_font = ImageFont.truetype(font_path, s) if font_path else font
        dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        bbox = dummy.textbbox((0, 0), longest_line, font=test_font, spacing=-12)
        if (bbox[2] - bbox[0]) < target_width:
            return test_font, s
    return font, size

def draw_text_on_image(base_img, text, font_path, font_size, color, stroke, stroke_w, shadow_off):
    """Composites text directly onto a PIL image"""
    # Work on a copy
    img = base_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    W, H = img.size
    
    target_w = W * 0.85
    font, final_size = get_scaled_font(text, font_path, font_size, target_w)
    
    # Calculate text block size
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_w, spacing=-12)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Center position
    x = (W - text_w) / 2 - bbox[0]
    y = (H - text_h) / 2 - bbox[1]
    
    # Draw Shadow
    if shadow_off > 0:
        draw.text((x + shadow_off, y + shadow_off), text, font=font, fill=stroke, align='center', spacing=-12)
    
    # Draw Main Text
    draw.text((x, y), text, font=font, fill=color, align='center', stroke_width=stroke_w, stroke_fill=stroke, spacing=-12)
    return img

def create_split_convergence(text, font_path, font_size, video_w, video_h, duration, start_time):
    # (Same function as before, kept for the render step)
    lines = text.split('\n')
    clips = []
    target_w = video_w * 0.85 
    longest_line = max(lines, key=len) if lines else text
    font, final_size = get_scaled_font(longest_line, font_path, font_size, target_w)
    
    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    line_heights = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font, stroke_width=v_stroke_width)
        line_heights.append((bbox[3] - bbox[1]) + 20)
    
    total_h = sum(line_heights)
    start_y_cursor = (video_h / 2) - (total_h / 2)
    
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
        final_x = (video_w / 2) - (w / 2)
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

# --- 6. RENDER FUNCTION (For final export) ---
def render_video(row, videos_dir, font_path, output_path, col_map):
    # (Simplified for brevity - assumes checks passed)
    filename = str(row.get(col_map['filename'])).strip()
    video_full_path = os.path.join(videos_dir, filename)
    
    try:
        clip = VideoFileClip(video_full_path)
        if not clip.duration: clip.duration = get_duration_ffprobe(video_full_path) or 10.0
        
        w, h = clip.size
        dur = clip.duration
        t1_dur, t2_start = dur * 0.25, dur * 0.25
        t2_dur, t3_start = dur * 0.55, dur * 0.80
        t3_dur = dur * 0.20

        # Intro
        txt1 = ImageClip(np.array(draw_text_on_image(Image.new("RGBA", (w,h)), "LAWRENCE\nWITH JACOB JEFFRIES", font_path, v_size_main, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset)))
        txt1 = txt1.set_duration(t1_dur).set_position('center').crossfadeout(0.2)
        
        # Middle
        city = str(row.get(col_map['city'], 'Unknown')).upper()
        content2 = f"{row.get('Date','')}\n{city}\n{row.get('Venue','')}".upper()
        if motion_profile == "Split Convergence":
            txt2 = create_split_convergence(content2, font_path, v_size_small, w, h, t2_dur, t2_start)
        else:
            base_img = Image.new("RGBA", (w,h))
            overlay = draw_text_on_image(base_img, content2, font_path, v_size_small, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset)
            txt2 = ImageClip(np.array(overlay)).set_duration(t2_dur)
            # Re-implement other motions if needed, or simple pos set
            txt2 = txt2.set_position('center').set_start(t2_start).crossfadein(0.2)

        # Outro
        content3 = f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper()
        if motion_profile == "Split Convergence":
            txt3 = create_split_convergence(content3, font_path, v_size_small, w, h, t3_dur, t3_start)
        else:
            overlay3 = draw_text_on_image(Image.new("RGBA", (w,h)), content3, font_path, v_size_small, TEXT_RGB, STROKE_RGB, v_stroke_width, v_shadow_offset)
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

col_files, col_preview = st.columns([1, 2])

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
        # --- PREVIEW LOGIC ---
        with col_files:
            st.markdown("---")
            st.subheader("📍 Select City")
            preview_idx = st.selectbox("Choose row to preview:", df.index, format_func=lambda x: f"{df.iloc[x].get(col_map['city'], 'Unknown')}")
            
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
                        # Find file in zip (handle subfolders)
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
            
            # 1. Cache the background frame
            if st.session_state.current_preview_file != video_file and os.path.exists(video_path):
                with st.spinner("Loading video frame..."):
                    try:
                        clip = VideoFileClip(video_path)
                        # Save frame 0 as PIL Image
                        st.session_state.preview_img_cache = Image.fromarray(clip.get_frame(0))
                        st.session_state.current_preview_file = video_file
                        clip.close()
                    except:
                        st.error("Failed to load video frame.")

            # 2. Real-time composite
            if st.session_state.preview_img_cache:
                # Text Content to Preview
                preview_text = f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper()
                
                # Draw
                final_preview = draw_text_on_image(
                    st.session_state.preview_img_cache, 
                    preview_text, 
                    font_path, 
                    v_size_small, # Using small size as this is usually the complex part
                    TEXT_RGB, 
                    STROKE_RGB, 
                    v_stroke_width, 
                    v_shadow_offset
                )
                
                st.image(final_preview, caption="Real-time Preview (Frame 0)", use_container_width=True)
            else:
                st.info("Upload files to see preview.")

        # --- BATCH RENDER SECTION ---
        st.markdown("---")
        st.subheader("🚀 BATCH PROCESSING")
        if st.button("RENDER ALL VIDEOS"):
            # (Standard Render Logic reused here)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            output_dir = os.path.join(st.session_state.temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            results = []
            files_to_zip = []
            
            # Extract everything first to be safe
            with zipfile.ZipFile(uploaded_zip, 'r') as z:
                z.extractall(st.session_state.temp_dir)

            total = len(df)
            for i, r in df.iterrows():
                c_name = str(r.get(col_map['city'])).replace(" ", "_")
                fname = str(r.get(col_map['filename']))
                out_name = f"Promo_{c_name}_{fname}"
                out_path = os.path.join(output_dir, out_name)
                
                status_text.text(f"Rendering {i+1}/{total}: {c_name}...")
                
                # Call Render
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
