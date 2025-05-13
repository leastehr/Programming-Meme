import random, textwrap, io, requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

# --- Page setup ---
st.set_page_config(page_title="Meme Generator", layout="wide")

# --- Custom CSS -------------------------------------------------------------
st.markdown("""
<style>
html, body { margin: 0; padding: 0; background: #ffffff; overflow-x: hidden; }

/* --- SIDEBAR --- */
section[data-testid="stSidebar"] {
  background-color: #2c3e50;
  height: 100vh;
  padding: 0 1rem 1rem;
  overflow: auto;
  box-sizing: border-box;
}
/* Default sidebar text */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label {
  color: #ffffff;
  font-family: "Segoe UI", sans-serif;
}
/* Expander text */
section[data-testid="stSidebar"] .stExpander div[role="button"],
section[data-testid="stSidebar"] .stExpander p,
section[data-testid="stSidebar"] .stExpander li {
  color: #ffffff !important;
}
/* Input + select text */
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] textarea {
  color: #133a5e;
  font-weight: 600;
}
section[data-testid="stSidebar"] .stSelectbox div[role="button"],
section[data-testid="stSidebar"] .stSelectbox span {
  color: #133a5e !important;
  font-weight: 600;
  background: #ffffff !important;
}
section[data-testid="stSidebar"] .stSelectbox ul {
  color: #133a5e !important;
}
/* Slider: white label, red ticks */
section[data-testid="stSidebar"] .stSlider label { color: #ffffff !important; }
section[data-testid="stSidebar"] .stSlider div[data-baseweb="slider"] *,
section[data-testid="stSidebar"] .stSlider span { color: #ff4c4c !important; }
/* Buttons */
section[data-testid="stSidebar"] button {
  background: #ff4c4c;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-size: 1rem;
  font-weight: 600;
}

/* --- MAIN --- */
.meme-title {
  font-size: 1.3rem;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 1rem;
  font-family: "Segoe UI", sans-serif;
}
.scaled-img-container img {
  height: auto;
  max-height: 60vh;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  border-radius: 8px;
}
.scaled-img-container img {
  max-height: 50vh;
  object-fit: contain;
  border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# --- Session defaults -------------------------------------------------------
for k, v in {"skips": 0, "template_data": None}.items():
    st.session_state.setdefault(k, v)

# --- Template fetch (cached) ------------------------------------------------
@st.cache_data
def get_templates():
    """Load meme templates from Imgflip and cache the result."""
    res = requests.get("https://api.imgflip.com/get_memes").json()
    return res.get("data", {}).get("memes", [])

templates = get_templates()

# --- Constants --------------------------------------------------------------
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
POSITION_OPTIONS = ["Top", "Centre", "Bottom", "Custom"]

# --- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.markdown("<h1 class='sidebar-title'>Meme Generator</h1>", unsafe_allow_html=True)
    st.markdown("## ⚙️ Controls")

    # Small how-to expander
    with st.expander("ℹ️ How to use", expanded=False):
        st.markdown(
            """
            1. *Choose a template* or keep pressing Select template until you like one.
            2. *Add your captions* below and pick a position for each.
            3. Tweak font size or auto-fit as you wish.
            4. Download your masterpiece 🎉
            """
        )

    # Template selector button
    if templates and st.button("Select template 🔄", key="rand_btn") and st.session_state["skips"] < 5:
        st.session_state["template_data"] = random.choice(templates)
        st.session_state["skips"] += 1

        # reset inserted text on new template
        for k in list(st.session_state.keys()):
            if k.startswith("txt"):
                st.session_state[k] = ""
                
    elif not templates:
        st.warning("Couldn't load templates. Check API connection.")
    st.markdown(f"Skips left: {5 - st.session_state['skips']}")

    # Caption inputs ---------------------------------------------------------
    num_caps = st.slider("Number of captions", 1, 5, 2)
    caption_boxes = []
    for i in range(num_caps):
        st.markdown(f"### Caption {i+1}")
        txt = st.text_input("Add your text here", key=f"txt{i}")

        # Position selector with URL persistence
        preset = st.query_params.get(f"pos{i}", "Top")
        idx = POSITION_OPTIONS.index(preset) if preset in POSITION_OPTIONS else 0
        selected = st.selectbox("Position", POSITION_OPTIONS, index=idx, key=f"pos_select{i}")
        if selected != preset:
            st.query_params[f"pos{i}"] = selected

        # Coordinates based on preset / custom sliders
        if selected == "Top":
            x_pct, y_pct = 50, 10
        elif selected == "Centre":
            x_pct, y_pct = 50, 50
        elif selected == "Bottom":
            x_pct, y_pct = 50, 90
        else:
            colx, coly = st.columns(2)
            x_pct = colx.slider("X %", 0, 100, int(st.session_state.get(f"x{i}", 50)), key=f"x{i}")
            y_pct = coly.slider("Y %", 0, 100, int(st.session_state.get(f"y{i}", 50)), key=f"y{i}")

        caption_boxes.append({"text": txt, "x": x_pct, "y": y_pct})

    # Typography controls ----------------------------------------------------
    base_font = st.slider("Base font size", 10, 100, 48)
    auto_fit = st.checkbox("Auto-fit width", value=True)

# --- Main content -----------------------------------------------------------
st.markdown('<div class="meme-title">Create your meme here</div>', unsafe_allow_html=True)


def draw_caption(im: Image.Image, txt: str, x_pct: int, y_pct: int, base: int, fit: bool) -> None:
    """Draw a single caption onto a PIL image."""
    draw = ImageDraw.Draw(im)
    fs = base
    # Shrink font size until it fits (if auto_fit is True)
    while fit and fs >= 12:
        f = ImageFont.truetype(FONT_PATH, fs)
        w = draw.multiline_textbbox((0, 0), textwrap.fill(txt.upper(), 25), font=f, spacing=4)[2]
        if w <= im.width * 0.95:
            break
        fs -= 2
    f = ImageFont.truetype(FONT_PATH, fs)
    wrapped = textwrap.fill(txt.upper(), 25)
    w, h = draw.multiline_textbbox((0, 0), wrapped, font=f, spacing=4)[2:]
    x = int(im.width * x_pct / 100) - w // 2
    y = int(im.height * y_pct / 100) - h // 2

    # Black outline for readability
    for dx, dy in [(-2, -2), (2, 2), (2, -2), (-2, 2)]:
        draw.multiline_text((x + dx, y + dy), wrapped, font=f, fill="black", spacing=4, align="center")
    # White fill
    draw.multiline_text((x, y), wrapped, font=f, fill="white", spacing=4, align="center")

# If we have a template selected, render it
if st.session_state.get("template_data"):
    meme_url = st.session_state["template_data"]["url"]
    img = Image.open(BytesIO(requests.get(meme_url).content)).convert("RGB")

    # Draw all captions
    for box in caption_boxes:
        if box["text"]:
            draw_caption(img, box["text"], box["x"], box["y"], base_font, auto_fit)

    # Display & download
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    st.markdown('<div class="scaled-img-container">', unsafe_allow_html=True)
    # use base64 image class as it allows in combination with markdown to properly set a max height value for the images,
    # disabling vertical scrolling, this is not supported by st.image()
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    # Embed in HTML with height limit
    st.markdown(f"""
    <div class="scaled-img-container">
        <img src="data:image/png;base64,{img_base64}" style="max-height: 60vh; width: auto; height: auto; object-fit: contain; border-radius: 8px;" />
    </div>
    """, unsafe_allow_html=True)

    st.download_button("⬇️ Download meme", buf, "meme.png", mime="image/png")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Click *Select template* in the sidebar to start.")