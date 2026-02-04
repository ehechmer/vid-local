import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import shutil
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
from PIL import Image, ImageFont, ImageDraw

#---1. BRANDING & STYLE CONFIGURATION
APP_NAME = "L&K Localizer"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#4FBDDB"
BACKGROUND_COLOR = "#0A1A1E"
UI_TEXT_COLOR = "#DCE4EA"

# VIDEO TEXT STYLING
TEXT_HEX_COLOR = 'white'      
STROKE_HEX_COLOR = 'black'    
STROKE_WIDTH = 4              
OVERLAY_OPACITY = 0.4         

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="centered")

#---2. UI STYLING
st.markdown(f"""
<style>
    .stApp {{ background-color: {BACKGROUND_COLOR}; color: {UI_TEXT_COLOR}; font-family: 'Helvetica Neue', sans-serif; }}
    h1 {{ color: {UI_TEXT_COLOR}; text-transform: uppercase; letter-spacing: 4px; text-align: center; font-size: 40px; }}
    h3 {{ color: {PRIMARY_COLOR}; font-weight: 600; text-transform: uppercase; text-align: center; margin-top: -20px; letter-spacing: 2px; }}
    .stButton>button {{ background-color: transparent; color: {PRIMARY_COLOR}; border: 2px solid {PRIMARY_COLOR}; padding: 10px; width: 100%; font-weight: bold; }}
    .stButton>button:hover {{ background-color: {PRIMARY_COLOR}; color: {BACKGROUND_COLOR}; }}
</style>
""", unsafe_allow_html=True)

#---3. HELPER: DYNAMIC COLUMN FINDER
def get_col(df, possible_names):
    for name in possible_names:
        for col in df.columns:
            if col.strip().lower() == name.lower():
                return col
    return None

#---4. VIDEO ENGINE
def create_pil_text_clip(text, font_path, font_size, color, stroke_width=STROKE_WIDTH, stroke_color=STROKE_HEX_COLOR):
    try:
        font = ImageFont.truetype(font_path, int(font_size)) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), text, font=font, align='center', stroke_width=stroke_width)
    w, h = int((bbox[2]-bbox[0])+60), int((bbox[3]-bbox[1])+60)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((int(30-bbox[0]), int(30-bbox[1])), text, font=font, fill=color, align='center', 
              stroke_width=stroke_width, stroke_fill=stroke_color)
    return ImageClip(np.array(img))

def render_video(row, videos_dir, font_path, output_path, col_map):
    fname_col = col_map.get('filename')
    city_col = col_map.get('city')
    filename = str(row.get(fname_col, '')).strip()
    video_full_path = os.path.join(videos_dir, filename)
    
    if not filename or not os.path.exists(video_full_path): 
        return False, f"File '{filename}' not found"

    try:
        clip = VideoFileClip(video_full_path)
        w, h = clip.size
        dur = clip.duration
        scale = 1.0 if (w / h) < 0.7 else 0.75
        overlay = ColorClip(size=(w, h), color=(0,0,0)).set_opacity(OVERLAY_OPACITY).set_duration(dur)
        
        txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(80*scale), TEXT_HEX_COLOR)
        txt1 = txt1.set_position('center').set_start(0).set_duration(dur*0.2).crossfadeout(0.3)
        
        city_name = str(row.get(city_col, 'Unknown')).upper()
        content2 = f"{row.get('Date','')}\n{city_name}\n{row.get('Venue','')}".upper()
        txt2 = create_pil_text_clip(content2, font_path, int(70*scale), TEXT_HEX_COLOR)
        txt2 = txt2.set_position(lambda t: ('center', (h/2 + 50) - (min(1, t/0.5) * 50))).set_start(dur*0.2).set_duration(dur*0.65).crossfadein(0.3)
        
        txt3 = create_pil_text_clip(f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper(), font_path, int(70*scale), TEXT_HEX_COLOR)
        txt3 = txt3.set_position('center').set_start(dur*0.85).set_duration(dur*0.15).crossfadein(0.2)

        final = CompositeVideoClip([clip, overlay, txt1, txt2, txt3])
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
        clip.close()
        return True, "Success"
    except Exception as e:
        return False, str(e)

#---5. UI LAYOUT
st.title(APP_NAME)
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    uploaded_zip = st.file_uploader("1. ZIP of Videos", type=["zip"])
    uploaded_font = st.file_uploader("2. Font (.ttf)", type=["ttf"])
with c2:
    uploaded_csv = st.file_uploader("3. Schedule (.csv)", type=["csv"])

if uploaded_zip and uploaded_csv:
    df = pd.read_csv(uploaded_csv)
    col_map = {
        'filename': get_col(df, ['Filename', 'File Name', 'Video', 'file']),
        'city': get_col(df, ['City', 'Location', 'Town'])
    }
    
    if not col_map['filename']:
        st.error("🚨 ERROR: Could not find a 'Filename' column in your CSV.")
    else:
        with st.expander("📊 STEP 4: VALIDATE FILENAMES"):
            if st.button("CHECK ZIP CONTENTS"):
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    zip_files = [os.path.basename(f) for f in z.namelist() if not f.endswith('/')]
                fname_col = col_map['filename']
                missing = [f for f in df[fname_col].tolist() if str(f).strip() not in zip_files]
                if missing: st.error(f"Missing {len(missing)} files.")
                else: st.success("All filenames found!")

        st.markdown("---")
        st.subheader("🔍 PREVIEW ENGINE")
        preview_row = st.selectbox("Select row", df.index, format_func=lambda x: f"{df.iloc[x].get(col_map['city'], 'Unknown')} ({df.iloc[x].get(col_map['filename'])})")
        
        if st.button("GENERATE PREVIEW"):
            base_dir = tempfile.mkdtemp()
            try:
                v_dir = os.path.join(base_dir, "v")
                os.makedirs(v_dir, exist_ok=True) #
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    for member in z.infolist():
                        if not member.is_dir():
                            member.filename = os.path.basename(member.filename)
                            z.extract(member, v_dir)
                f_p = os.path.join(base_dir, "f.ttf") if uploaded_font else None
                if f_p: 
                    with open(f_p, "wb") as f: f.write(uploaded_font.read())
                with st.spinner("Rendering..."):
                    out = os.path.join(base_dir, "p.mp4")
                    success, msg = render_video(df.iloc[preview_row], v_dir, f_p, out, col_map)
                    if success: st.video(out)
                    else: st.error(f"Error: {msg}")
            finally: shutil.rmtree(base_dir)

        st.subheader("🚀 BATCH PROCESSING")
        if st.button("RUN FULL BATCH"):
            base_dir = tempfile.mkdtemp()
            try:
                v_dir, o_dir = os.path.join(base_dir, "v"), os.path.join(base_dir, "o")
                os.makedirs(v_dir, exist_ok=True); os.makedirs(o_dir, exist_ok=True) #
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    for m in z.infolist():
                        if not m.is_dir():
                            m.filename = os.path.basename(m.filename)
                            z.extract(m, v_dir)

                f_p = os.path.join(base_dir, "f.ttf") if uploaded_font else None
                if f_p: 
                    with open(f_p, "wb") as f: f.write(uploaded_font.read())

                processed, log_data = [], []
                status_container = st.empty()
                prog = st.progress(0)
                
                for i, row in df.iterrows():
                    city = str(row.get(col_map['city'], 'Unknown'))
                    orig_fname = str(row.get(col_map['filename'], 'video'))
                    # Added original filename to avoid overwriting files with the same city
                    out_name = f"Promo_{city.replace(' ', '_')}_{orig_fname}"
                    out_path = os.path.join(o_dir, out_name)
                    
                    success, msg = render_video(row, v_dir, f_p, out_path, col_map)
                    log_data.append({"City": city, "Status": "✅" if success else f"❌ {msg}"})
                    status_container.table(log_data)
                    if success: processed.append(out_path)
                    prog.progress((i + 1) / len(df))

                if processed:
                    z_path = os.path.join(base_dir, "Results.zip")
                    with zipfile.ZipFile(z_path, 'w') as z:
                        for f in processed: z.write(f, os.path.basename(f)) #
                    st.download_button("Download All Videos", open(z_path, "rb"), "Tour_Assets.zip")
            finally: shutil.rmtree(base_dir)
