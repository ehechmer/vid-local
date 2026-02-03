import streamlit as st
import pandas as pd
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import tempfile
import os
import zipfile

# --- 1. BRANDING CONFIGURATION (EDIT COLORS HERE) ---
APP_NAME = "vid_local"
COMPANY_NAME = "LOCH & KEY PRODUCTIONS"
PRIMARY_COLOR = "#C5A059"  # <--- REPLACE with your exact Hex Code (e.g., #FF0000)
BACKGROUND_COLOR = "#0e0e0e" # Dark Cinema Background
TEXT_COLOR = "#ffffff"

# --- 2. PAGE SETUP ---
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="centered"
)

# --- 3. CUSTOM CSS (Loch & Key Branding) ---
st.markdown(f"""
    <style>
    /* Main Background */
    .stApp {{
        background-color: {BACKGROUND_COLOR};
        color: {TEXT_COLOR};
        font-family: 'Helvetica Neue', sans-serif;
    }}

    /* Header Styling */
    h1 {{
        color: {TEXT_COLOR};
        font-weight: 300;
        letter-spacing: 4px;
        text-transform: uppercase;
        font-size: 40px !important;
        text-align: center;
        margin-bottom: 0px;
    }}
    h3 {{
        color: {PRIMARY_COLOR};
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        font-size: 14px !important;
        text-align: center;
        margin-top: -20px;
        margin-bottom: 40px;
        opacity: 0.8;
    }}

    /* Button Styling */
    .stButton>button {{
        background-color: transparent;
        color: {PRIMARY_COLOR};
        border: 2px solid {PRIMARY_COLOR};
        border-radius: 0px; /* Sharp edges for production feel */
        padding: 15px 30px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        width: 100%;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        background-color: {PRIMARY_COLOR};
        color: {BACKGROUND_COLOR};
        border: 2px solid {PRIMARY_COLOR};
    }}

    /* File Uploader Styling */
    .stFileUploader label {{
        color: {PRIMARY_COLOR};
        font-weight: bold;
    }}

    /* Success Message */
    .stSuccess {{
        background-color: rgba(197, 160, 89, 0.2);
        color: white;
        border-left: 5px solid {PRIMARY_COLOR};
    }}
    </style>
""", unsafe_allow_html=True)

# --- 4. VIDEO ENGINE ---
def process_video_batch(df, video_path, font_path, temp_dir):
    generated_paths = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    clip = VideoFileClip(video_path)
    font_to_use = font_path if font_path else 'Arial'

    for i, row in df.iterrows():
        city_name = str(row['City']).upper()
        status_text.markdown(f"**PROCESSING:** {city_name}")

        # --- EDIT YOUR TEXT LAYOUT HERE ---

        # 1. TOP TEXT (Band Name)
        txt1 = TextClip("LAWRENCE\nWITH JACOB JEFFRIES", font=font_to_use, fontsize=80, color='white', stroke_color='black', stroke_width=2)
        txt1 = txt1.set_position(('center', 'center')).set_start(0).set_duration(4)

        # 2. MIDDLE TEXT (Date/Venue)
        content2 = f"{row['Date']}\n{city_name}\n{row['Venue']}"
        txt2 = TextClip(content2.upper(), font=font_to_use, fontsize=70, color='white', stroke_color='black', stroke_width=2)
        txt2 = txt2.set_position(('center', 'center')).set_start(4).set_duration(13)

        # 3. END TEXT (Link)
        content3 = f"TICKETS ON SALE NOW\n{row['Ticket_Link']}"
        txt3 = TextClip(content3.upper(), font=font_to_use, fontsize=70, color='white', stroke_color='black', stroke_width=2)
        txt3 = txt3.set_position(('center', 'center')).set_start(17).set_duration(clip.duration - 17)

        # Composite
        final = CompositeVideoClip([clip, txt1, txt2, txt3])

        # Output
        output_filename = f"Promo_{city_name.replace(' ', '')}.mp4"
        output_path = os.path.join(temp_dir, output_filename)

        # Optimized for Cloud Speed (Ultrafast preset)
        final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')

        generated_paths.append(output_path)
        progress_bar.progress((i + 1) / len(df))

    clip.close()
    return generated_paths

# --- 5. FRONT END ---
st.title("VID_LOCAL")
st.markdown(f"<h3>{COMPANY_NAME}</h3>", unsafe_allow_html=True)

# Layout
with st.container():
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ASSETS")
        uploaded_video = st.file_uploader("Clean Video File (.mp4)", type=["mp4"])
        uploaded_font = st.file_uploader("Font File (.ttf) [Optional]", type=["ttf"])

    with col2:
        st.markdown("#### DATA")
        uploaded_csv = st.file_uploader("Tour Schedule (.csv)", type=["csv"])
        if uploaded_csv:
            st.caption("✅ Data Loaded Successfully")

if uploaded_video and uploaded_csv:
    st.markdown("---")
    if st.button("INITIALIZE RENDER ENGINE"):
        with tempfile.TemporaryDirectory() as temp_dir:

            # Setup Temp Files
            tfile_vid = os.path.join(temp_dir, "input.mp4")
            with open(tfile_vid, "wb") as f: f.write(uploaded_video.read())

            font_path = None
            if uploaded_font:
                font_path = os.path.join(temp_dir, "custom.ttf")
                with open(font_path, "wb") as f: f.write(uploaded_font.read())

            df = pd.read_csv(uploaded_csv)

            try:
                files = process_video_batch(df, tfile_vid, font_path, temp_dir)

                # Zip and Download
                zip_path = os.path.join(temp_dir, f"{APP_NAME}_Output.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in files:
                        zipf.write(file, os.path.basename(file))

                st.balloons()
                st.success("RENDER COMPLETE. DOWNLOADING ASSETS.")

                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="⬇️ DOWNLOAD ZIP PACKAGE",
                        data=f,
                        file_name=f"{APP_NAME}_Assets.zip",
                        mime="application/zip"
                    )

            except Exception as e:
                st.error(f"Render Error: {str(e)}")
