import os
import json
import random
import asyncio
import requests
import math
import shutil
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
import edge_tts

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
)

import moviepy.video.fx as vfx

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not GROQ_KEY:
    raise ValueError(
        "GROQ_API_KEY missing. Add GROQ_API_KEY=... to your .env file."
    )

if not PEXELS_API_KEY:
    raise ValueError(
        "PEXELS_API_KEY missing. Add PEXELS_API_KEY=... to your .env file."
    )

groq_client = Groq(api_key=GROQ_KEY)

# ------------------------------------------------------------
# Folders
# ------------------------------------------------------------

OUTPUT_DIR = Path("output")
CLIPS_DIR = OUTPUT_DIR / "clips"
AUDIO_DIR = OUTPUT_DIR / "audio"
CAPTION_DIR = OUTPUT_DIR / "captions"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"

SFX_DIR = Path("sfx")

for directory in [
    OUTPUT_DIR,
    CLIPS_DIR,
    AUDIO_DIR,
    CAPTION_DIR,
    THUMBNAIL_DIR,
    SFX_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Files
# ------------------------------------------------------------

BGM_FILE = "bgm.mp3"

WHOOSH_FILE = SFX_DIR / "whoosh.mp3"
IMPACT_FILE = SFX_DIR / "impact.mp3"
HEARTBEAT_FILE = SFX_DIR / "heartbeat.mp3"
HIT_FILE = SFX_DIR / "hit.mp3"

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"


# ------------------------------------------------------------
# Video
# ------------------------------------------------------------

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

TARGET_MIN_DURATION = 22
TARGET_MAX_DURATION = 35

VOICE = "hi-IN-MadhurNeural"

# Faster than previous version.
VOICE_RATE = "+16%"
VOICE_PITCH = "-2Hz"


# ============================================================
# MYSTERY TOPICS
# ============================================================

MYSTERY_TOPICS = [
    "Bhangarh Fort Rajasthan mystery",
    "Kuldhara abandoned village Rajasthan mystery",
    "Roopkund skeleton lake Uttarakhand mystery",
    "Konark Sun Temple Odisha mystery",
    "Meenakshi Temple Madurai hidden history",
    "Ellora Caves Maharashtra unexplained mystery",
    "Ajanta Caves Maharashtra hidden history",
    "Golconda Fort Hyderabad secret tunnels",
    "Daulatabad Fort Maharashtra secret history",
    "Lepakshi Temple Andhra Pradesh mystery",
    "Padmanabhaswamy Temple Kerala hidden history",
    "Jagannath Temple Puri unexplained mystery",
    "Brihadeeswarar Temple Tamil Nadu mystery",
    "Rani ki Vav Gujarat hidden history",
    "Lothal Gujarat ancient civilization mystery",
    "Dholavira Gujarat ancient city mystery",
    "Mohenjo-daro Indian civilization mystery",
    "Nalanda Bihar ancient university mystery",
    "Vikramshila Bihar ancient university mystery",
    "Sanchi Stupa Madhya Pradesh hidden history",
    "Khajuraho Madhya Pradesh hidden history",
    "Hampi Karnataka lost city mystery",
    "Vijayanagara Empire mystery",
    "Shani Shingnapur Maharashtra mystery",
    "Shiv Temple India ancient architecture mystery",
    "Kailasa Temple Ellora impossible construction mystery",
    "Iron Pillar Delhi rust mystery",
    "Delhi Sultanate forgotten mystery",
    "Red Fort Delhi hidden history",
    "Qutub Minar Delhi hidden history",
    "Agrasen ki Baoli Delhi mystery",
    "Jaisalmer Fort Rajasthan hidden history",
    "Kumbhalgarh Fort Rajasthan secret history",
    "Mehrangarh Fort Rajasthan mystery",
    "Chittorgarh Fort Rajasthan hidden history",
    "Amer Fort Jaipur secret passage mystery",
    "Bhangarh village folklore mystery",
    "Indian freedom movement unsolved mystery",
    "Subhas Chandra Bose disappearance mystery",
    "Lal Bahadur Shastri death mystery",
    "Netaji Subhas Chandra Bose historical mystery",
    "Indian royal family historical mystery",
    "Indian ancient manuscript mystery",
    "Indian archaeological discovery mystery",
    "Indian temple underground tunnel mystery",
    "Indian lost city historical mystery",
    "Indian shipwreck historical mystery",
    "Indian haunted fort historical mystery",
    "Indian cave civilization mystery",
    "Indian ancient engineering mystery",
    "Indian astronomy ancient history mystery",
    "Indian stepwell hidden history",
    "Indian railway historical mystery",
    "Indian village disappearance folklore mystery",
    "Indian historical artifact mystery",
]


# ============================================================
# STORY GENERATOR
# ============================================================

def generate_mystery_story():

    topic = random.choice(MYSTERY_TOPICS)

    print("\n" + "=" * 75)
    print("🧠 GENERATING HIGH-RETENTION MYSTERY SHORT")
    print("🎯 Topic:", topic)
    print("=" * 75)

    prompt = f"""
You are a professional Hindi YouTube Shorts writer for an INDIA-ONLY channel.
Your niche is Indian dark history, Indian mysteries, Indian facts, Indian archaeology,
and unusual stories from India's past.

ABSOLUTE INDIA-ONLY RULE:
- The story MUST be about INDIA.
- The people, place, event, object, history, archaeology, folklore or mystery MUST be connected to India.
- NEVER choose or mention Bermuda Triangle, Egypt, Rome, Vikings, Europe, America, Japan,
  or any other non-Indian mystery as the main topic.
- Do not use foreign examples just for comparison.
- Pexels queries MUST be searchable Indian visuals. Add India, the Indian state/city,
  or a specific Indian landmark whenever possible.
- If the topic is folklore or a disputed claim, clearly label it as folklore/theory and do not present it as fact.

TOPIC:
{topic}

Create ONE highly engaging Hindi YouTube Short.

TARGET LENGTH:
20-32 seconds. Keep the spoken delivery compact and fast.

FACTUAL RULE:
Only present established information as fact.
When evidence is uncertain use wording such as:
"एक सिद्धांत के अनुसार..."
"कुछ इतिहासकार मानते हैं..."
"लोककथाओं के अनुसार..."
"आज तक इसका निश्चित जवाब नहीं मिला..."
"इस दावे की स्वतंत्र पुष्टि नहीं हुई है..."

DO NOT invent dates, people, discoveries, scientific claims, quotes or evidence.
If the topic is a popular Indian legend, separate legend from documented history.

==========================================================
VIRAL RETENTION STRUCTURE
==========================================================

0-2 SEC — EXTREME HOOK:
The first spoken line MUST create a strong curiosity gap immediately.
It should make the viewer think: "आगे क्या हुआ?"
Use a concrete Indian place/person/object when possible.

Good hook style:
"राजस्थान की इस जगह पर लोग रात में जाना क्यों छोड़ देते हैं?"
"भारत की इस झील में मिले कंकालों का राज आज तक पूरी तरह नहीं सुलझा।"
"दिल्ली में एक ऐसी बावड़ी है, जिसके बारे में इतिहास आज भी सवाल छोड़ता है।"
"इस भारतीय मंदिर को देखकर आज भी एक सवाल उठता है—इसे बनाया कैसे गया?"

NEVER begin with:
"आज हम बात करेंगे..."
"क्या आप जानते हैं..."
"नमस्कार दोस्तों..."
"दोस्तों आज की वीडियो में..."

2-6 SEC — MYSTERY SETUP:
Give the most surprising Indian fact quickly.

6-18 SEC — CLUE CHAIN:
Reveal one new fact or clue every sentence.
Use short spoken sentences. No filler.

18-27 SEC — STRONGEST REVELATION:
Give the most interesting documented clue, contradiction or historical detail.

FINAL 2-4 SEC — CURIOSITY PAYOFF:
End with a powerful unanswered question that invites comments.
Example style:
"लेकिन अगर कहानी इतनी सी नहीं है... तो असली वजह क्या थी?"

IMPORTANT:
Do not give away every detail too early.
Build a curiosity chain:
HOOK → MYSTERY → CLUE → BIGGER CLUE → REVELATION → UNANSWERED QUESTION

==========================================================
LANGUAGE + VOICE
==========================================================

Natural spoken Hindi.
Short sentences.
Fast, energetic delivery.
Use punctuation for dramatic micro-pauses.
Avoid long sentences and filler words.
The first sentence must sound strong even without context.

==========================================================
VISUAL STORYTELLING
==========================================================

Create exactly 7 visual beats.
Each beat should be roughly 2-5 seconds.
Change visuals frequently.
Every visual must directly match the narration.

IMPORTANT INDIA VISUAL RULE:
Every pexels_query must target India or an Indian location/object.
Use queries like:
"Bhangarh Fort Rajasthan India night"
"Kuldhara village Rajasthan India"
"Roopkund lake Uttarakhand India"
"Indian ancient temple India"
"Rajasthan fort India aerial"
"old Indian map close up"
"Indian archaeological excavation"
"Delhi old monument India"
"Hampi Karnataka India ruins"
"Kerala temple India"

Do NOT use generic foreign visuals such as pyramids, Egyptian temples,
European castles, Viking ships, New York, etc.
If an exact historical scene is unavailable on Pexels, use a visually relevant
Indian location, monument, map, manuscript, excavation or landscape.

==========================================================
ORIGINAL EDITING
==========================================================

The final video should feel intentionally edited, not like a raw stock compilation.
Use:
- rapid cuts
- punch-in zooms
- subtle movement
- strong opening frame
- short caption changes
- contextual text cards
- atmospheric overlays
- SFX moments
- low-volume suspense BGM
- final question

==========================================================
CAPTIONS
==========================================================

Create short captions, maximum 4 words.
Use curiosity-heavy Hindi such as:
"राज़ अभी बाकी है"
"लेकिन क्यों?"
"सबसे बड़ा सवाल"
"सच्चाई क्या थी?"
"इतिहास चुप है"

==========================================================
OUTPUT
==========================================================

Return ONLY valid JSON.

Format:
{{
  "topic": "...",
  "title": "...",
  "description": "...",
  "hook": "...",
  "scenes": [
    {{
      "scene_number": 1,
      "start_time": 0,
      "end_time": 3,
      "narration": "...",
      "pexels_query": "...",
      "caption": "...",
      "sfx": "impact"
    }}
  ]
}}

TITLE:
Maximum approximately 55 characters.
Make it curiosity-driven and clearly Indian.
Examples:
"इस किले का राज़ आज तक नहीं खुला 😱 #Shorts"
"भारत की इस झील में मिले कंकाल क्यों? 😱 #Shorts"

Use relevant hashtags such as:
#Shorts #IndianMystery #IndianHistory #IndiaFacts

DESCRIPTION:
Natural Hindi description about the Indian story.
Do not keyword stuff.
Mention that disputed claims are presented as theories/folklore when applicable.
End with a natural question for viewers.

The final scene MUST contain a question that encourages comments.
"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a factual, high-retention Hindi "
                    "dark-history YouTube Shorts writer."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.82,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    data = json.loads(content)

    if "scenes" not in data:
        raise RuntimeError("Story JSON does not contain scenes.")

    data = validate_indian_story(data)

    print("\n🎬 TITLE:")
    print(data.get("title", "Untitled"))

    print("\n🎯 HOOK:")
    print(data.get("hook", ""))

    return data


# ============================================================
# INDIA-ONLY VISUAL GUARD
# ============================================================

FORBIDDEN_FOREIGN_TERMS = [
    "bermuda", "dyatlov", "roanoke", "mary celeste", "tutankhamun",
    "egypt", "egyptian", "nazca", "antikythera", "voynich", "oak island",
    "atlantis", "stonehenge", "jack the ripper", "amelia earhart", "d.b. cooper",
    "pompeii", "roman empire", "viking", "europe", "america", "new york",
    "london", "paris", "japan", "china", "greece", "mesopotamia"
]


def ensure_india_query(query):
    """Keep stock-footage searches focused on India."""
    query = str(query or "").strip()
    lowered = query.lower()

    if any(term in lowered for term in FORBIDDEN_FOREIGN_TERMS):
        raise ValueError(f"Non-Indian visual query rejected: {query}")

    india_terms = [
        "india", "indian", "rajasthan", "delhi", "uttarakhand", "odisha",
        "karnataka", "kerala", "tamil nadu", "andhra pradesh", "telangana",
        "maharashtra", "gujarat", "bihar", "madhya pradesh", "west bengal",
        "punjab", "assam", "goa", "hampi", "varanasi", "jaipur", "agra",
        "hyderabad", "mumbai", "kolkata", "chennai", "puri", "konark"
    ]

    if not any(term in lowered for term in india_terms):
        query = f"India {query}"

    return query


def validate_indian_story(data):
    """Reject an AI response if it drifts away from the India-only niche."""
    topic = str(data.get("topic", ""))
    title = str(data.get("title", ""))
    description = str(data.get("description", ""))
    combined = f"{topic} {title} {description}".lower()

    if any(term in combined for term in FORBIDDEN_FOREIGN_TERMS):
        raise ValueError("Generated story contains a non-Indian topic. Regenerate it.")

    if not any(term in combined for term in [
        "india", "indian", "भारत", "भारतीय", "rajasthan", "delhi", "uttarakhand",
        "odisha", "karnataka", "kerala", "tamil", "maharashtra", "gujarat",
        "bihar", "madhya pradesh", "andhra", "telangana", "punjab", "assam"
    ]):
        raise ValueError("Generated story does not clearly identify India.")

    scenes = data.get("scenes", [])
    if len(scenes) != 7:
        raise ValueError(f"Expected exactly 7 scenes, got {len(scenes)}")

    for scene in scenes:
        scene["pexels_query"] = ensure_india_query(scene.get("pexels_query", ""))

    return data


# ============================================================
# PEXELS SEARCH
# ============================================================

def search_pexels_video(query):

    print(f"\n🔎 PEXELS SEARCH: {query}")

    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": query,
        "per_page": 20,
        "orientation": "portrait",
        "size": "large",
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code != 200:

            print(
                "❌ Pexels error:",
                response.status_code,
            )

            return None

        data = response.json()

        videos = data.get("videos", [])

        # ----------------------------------------------------
        # Fallback to landscape
        # ----------------------------------------------------

        if not videos:

            print(
                "⚠️ No portrait footage. "
                "Trying landscape..."
            )

            params["orientation"] = "landscape"

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                return None

            data = response.json()

            videos = data.get("videos", [])

        if not videos:
            return None

        candidates = []

        for video in videos:

            files = video.get(
                "video_files",
                []
            )

            for file in files:

                width = file.get(
                    "width"
                ) or 0

                height = file.get(
                    "height"
                ) or 0

                link = file.get("link")

                if not link:
                    continue

                # Prefer useful resolution.
                if width >= 720 or height >= 720:

                    candidates.append(
                        {
                            "url": link,
                            "width": width,
                            "height": height,
                            "duration": video.get(
                                "duration",
                                0
                            ),
                        }
                    )

        if not candidates:
            return None

        # Prefer vertical.
        vertical = [
            x
            for x in candidates
            if x["height"] > x["width"]
        ]

        if vertical:
            candidates = vertical

        # Prefer higher resolution.
        candidates.sort(
            key=lambda x: (
                x["width"] * x["height"]
            ),
            reverse=True,
        )

        # Pick from top candidates to avoid always selecting
        # the exact same clip.
        top_candidates = candidates[
            :min(8, len(candidates))
        ]

        selected = random.choice(
            top_candidates
        )

        print(
            "✅ Selected:",
            selected["width"],
            "x",
            selected["height"],
        )

        return selected

    except Exception as e:

        print(
            "❌ Pexels request failed:",
            e,
        )

        return None


# ============================================================
# DOWNLOAD
# ============================================================

def download_video(url, filename):

    print(
        f"⬇️ Downloading {filename}"
    )

    path = CLIPS_DIR / filename

    try:

        with requests.get(
            url,
            stream=True,
            timeout=120,
        ) as response:

            if response.status_code != 200:

                print(
                    "❌ Download failed:",
                    response.status_code,
                )

                return None

            with open(
                path,
                "wb",
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

        print(
            "✅ Saved:",
            path,
        )

        return str(path)

    except Exception as e:

        print(
            "❌ Download error:",
            e,
        )

        return None


# ============================================================
# SCENE VIDEO
# ============================================================

def get_scene_video(
    scene_number,
    query,
):

    result = search_pexels_video(
        query
    )

    if not result:

        print(
            f"⚠️ Scene {scene_number}: "
            "No suitable footage."
        )

        return None

    filename = (
        f"scene_{scene_number}.mp4"
    )

    return download_video(
        result["url"],
        filename,
    )


# ============================================================
# VOICE
# ============================================================

async def create_voice(
    text,
    output_file,
):

    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
    )

    await communicate.save(
        output_file
    )


def generate_voice(
    text,
    scene_number,
):

    filename = (
        AUDIO_DIR /
        f"voice_{scene_number}.mp3"
    )

    print(
        f"🎙️ Generating fast male Hindi voice "
        f"scene {scene_number}"
    )

    asyncio.run(
        create_voice(
            text,
            str(filename),
        )
    )

    return str(filename)


# ============================================================
# FONT
# ============================================================

def find_font():

    fonts = [

        "C:/Windows/Fonts/NirmalaB.ttf",

        "C:/Windows/Fonts/mangal.ttf",

        "C:/Windows/Fonts/arialbd.ttf",

    ]

    for font in fonts:

        if os.path.exists(font):
            return font

    return None


# ============================================================
# CAPTION IMAGE
# ============================================================

def create_caption_image(
    text,
    filename,
    emphasis=False,
):

    image = Image.new(
        "RGBA",
        (
            VIDEO_WIDTH,
            360,
        ),
        (
            0,
            0,
            0,
            0,
        ),
    )

    draw = ImageDraw.Draw(
        image
    )

    font_path = find_font()

    if font_path:

        font_size = (
            78
            if emphasis
            else 68
        )

        font = ImageFont.truetype(
            font_path,
            font_size,
        )

    else:

        font = ImageFont.load_default()

    # --------------------------------------------------------
    # Word wrapping
    # --------------------------------------------------------

    words = str(text).split()

    lines = []

    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

        if len(test) > 22:

            if current:
                lines.append(
                    current
                )

            current = word

        else:

            current = test

    if current:
        lines.append(current)

    lines = lines[:2]

    total_height = (
        len(lines) * 90
    )

    y = (
        180 -
        total_height // 2
    )

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font,
        )

        text_width = (
            bbox[2] -
            bbox[0]
        )

        x = (
            VIDEO_WIDTH -
            text_width
        ) // 2

        # Shadow
        draw.text(
            (
                x + 5,
                y + 5,
            ),
            line,
            font=font,
            fill="black",
            stroke_width=12,
            stroke_fill="black",
        )

        # Main text
        draw.text(
            (
                x,
                y,
            ),
            line,
            font=font,
            fill="white",
            stroke_width=5,
            stroke_fill="black",
        )

        y += 90

    image.save(
        filename
    )

    return filename


# ============================================================
# PREPARE SHORTS CLIP
# ============================================================

def prepare_clip_for_shorts(
    clip
):

    width = clip.w
    height = clip.h

    target_ratio = (
        VIDEO_WIDTH /
        VIDEO_HEIGHT
    )

    current_ratio = (
        width /
        height
    )

    if current_ratio > target_ratio:

        new_width = int(
            height *
            target_ratio
        )

        x1 = (
            width -
            new_width
        ) // 2

        clip = clip.cropped(
            x1=x1,
            x2=x1 + new_width,
        )

    else:

        new_height = int(
            width /
            target_ratio
        )

        y1 = (
            height -
            new_height
        ) // 2

        clip = clip.cropped(
            y1=y1,
            y2=y1 + new_height,
        )

    clip = clip.resized(
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
    )

    return clip


# ============================================================
# RAPID CUT CREATOR
# ============================================================

def create_rapid_segments(
    video,
    target_duration,
):

    """
    Creates several short sections from one stock clip.

    This prevents one stock clip from remaining visually
    unchanged for a long time.
    """

    if video.duration <= 0:
        return []

    segments = []

    # Usually 2-3 seconds per visual beat.
    segment_count = max(
        2,
        int(
            math.ceil(
                target_duration /
                2.5
            )
        ),
    )

    segment_duration = (
        target_duration /
        segment_count
    )

    for i in range(
        segment_count
    ):

        if video.duration <= segment_duration:

            source_start = 0

        else:

            available = (
                video.duration -
                segment_duration
            )

            source_start = (
                available *
                i /
                max(
                    1,
                    segment_count - 1
                )
            )

        source_end = (
            source_start +
            segment_duration
        )

        source_end = min(
            source_end,
            video.duration,
        )

        if source_end <= source_start:
            continue

        piece = video.subclipped(
            source_start,
            source_end,
        )

        # Alternate crop positioning.
        piece = prepare_clip_for_shorts(
            piece
        )

        # ----------------------------------------------------
        # Fast subtle zoom.
        # ----------------------------------------------------

        try:

            if i % 3 == 0:

                piece = piece.with_effects(
                    [
                        vfx.CrossFadeIn(
                            0.08
                        )
                    ]
                )

        except Exception:
            pass

        segments.append(piece)

    return segments


# ============================================================
# SFX
# ============================================================

def load_sfx(
    effect_name
):

    mapping = {

        "whoosh":
            WHOOSH_FILE,

        "impact":
            IMPACT_FILE,

        "heartbeat":
            HEARTBEAT_FILE,

        "hit":
            HIT_FILE,
    }

    file_path = mapping.get(
        effect_name
    )

    if not file_path:
        return None

    if not file_path.exists():
        return None

    return str(file_path)


# ============================================================
# AUDIO HELPERS
# ============================================================

def make_looped_audio(
    audio,
    duration,
):

    if audio.duration >= duration:

        return audio.subclipped(
            0,
            duration,
        )

    pieces = []

    remaining = duration

    while remaining > 0:

        part_duration = min(
            audio.duration,
            remaining,
        )

        pieces.append(
            audio.subclipped(
                0,
                part_duration,
            )
        )

        remaining -= part_duration

    return concatenate_audio_clips(
        pieces
    )


def concatenate_audio_clips(
    clips
):

    """
    MoviePy 2 compatible audio concatenation.
    """

    if not clips:
        return None

    if len(clips) == 1:
        return clips[0]

    from moviepy import (
        concatenate_audioclips
    )

    return concatenate_audioclips(
        clips
    )


# ============================================================
# BUILD ONE SCENE
# ============================================================

def build_scene(
    video_path,
    audio_path,
    caption,
    scene_number,
    sfx_name=None,
):

    print(
        f"\n🎬 Building scene "
        f"{scene_number}"
    )

    narration_audio = AudioFileClip(
        audio_path
    )

    duration = (
        narration_audio.duration
    )

    source_video = VideoFileClip(
        video_path
    )

    # --------------------------------------------------------
    # Make sure video is long enough.
    # --------------------------------------------------------

    if (
        source_video.duration <
        duration
    ):

        loops = int(
            duration /
            max(
                source_video.duration,
                0.1,
            )
        ) + 1

        video = concatenate_videoclips(
            [source_video] * loops,
            method="compose",
        )

    else:

        video = source_video

    video = video.subclipped(
        0,
        min(
            duration,
            video.duration,
        ),
    )

    # --------------------------------------------------------
    # Rapid visual changes
    # --------------------------------------------------------

    rapid_segments = create_rapid_segments(
        video,
        duration,
    )

    if rapid_segments:

        video = concatenate_videoclips(
            rapid_segments,
            method="compose",
        )

        video = video.subclipped(
            0,
            min(
                duration,
                video.duration,
            ),
        )

    else:

        video = prepare_clip_for_shorts(
            video
        )

    # --------------------------------------------------------
    # Caption
    # --------------------------------------------------------

    caption_file = (
        CAPTION_DIR /
        f"caption_{scene_number}.png"
    )

    create_caption_image(
        caption,
        str(caption_file),
        emphasis=(
            scene_number == 1
        ),
    )

    caption_image = (
        Image.open(
            caption_file
        )
        .convert("RGBA")
    )

    caption_array = __import__(
        "numpy"
    ).array(
        caption_image
    )

    from moviepy import ImageClip

    caption_clip = (
        ImageClip(
            caption_array
        )
        .with_duration(
            duration
        )
        .with_position(
            ("center", "center")
        )
    )

    # --------------------------------------------------------
    # Add audio
    # --------------------------------------------------------

    audio_layers = [
        narration_audio
    ]

    sfx_file = load_sfx(
        sfx_name
    )

    if sfx_file:

        try:

            sfx = AudioFileClip(
                sfx_file
            )

            sfx = sfx.with_volume_scaled(
                0.28
            )

            # Place SFX near beginning
            # for impact.
            if sfx.duration > 0.9:

                sfx = sfx.subclipped(
                    0,
                    min(
                        0.9,
                        sfx.duration,
                    )
                )

            sfx = sfx.with_start(
                0.02
            )

            audio_layers.append(
                sfx
            )

        except Exception as e:

            print(
                "⚠️ SFX skipped:",
                e,
            )

    combined_audio = (
        CompositeAudioClip(
            audio_layers
        )
    )

    # --------------------------------------------------------
    # Composite video + caption
    # --------------------------------------------------------

    from moviepy import CompositeVideoClip

    final_scene = CompositeVideoClip(
        [
            video,
            caption_clip,
        ],
        size=(
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
        ),
    )

    final_scene = final_scene.with_audio(
        combined_audio
    )

    return final_scene


# ============================================================
# BGM
# ============================================================

def add_background_music(
    final_video
):

    if not os.path.exists(
        BGM_FILE
    ):

        print(
            "⚠️ bgm.mp3 not found."
        )

        return final_video

    print(
        "🎵 Adding suspense BGM..."
    )

    bgm = AudioFileClip(
        BGM_FILE
    )

    bgm = make_looped_audio(
        bgm,
        final_video.duration,
    )

    # Keep narration clearly audible.
    bgm = bgm.with_volume_scaled(
        0.045
    )

    if final_video.audio:

        audio = CompositeAudioClip(
            [
                final_video.audio,
                bgm,
            ]
        )

    else:

        audio = bgm

    return final_video.with_audio(
        audio
    )


# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(
    video_path,
    title,
):

    print(
        "\n🖼️ Creating thumbnail..."
    )

    video = VideoFileClip(
        video_path
    )

    # Select a dramatic early frame.
    frame_time = min(
        1.5,
        max(
            0,
            video.duration - 0.1,
        ),
    )

    frame = video.get_frame(
        frame_time
    )

    image = Image.fromarray(
        frame
    ).convert("RGB")

    image = image.resize(
        (
            1280,
            720,
        )
    )

    # Dramatic contrast.
    image = image.filter(
        ImageFilter.SHARPEN
    )

    draw = ImageDraw.Draw(
        image
    )

    font_path = find_font()

    if font_path:

        font = ImageFont.truetype(
            font_path,
            72,
        )

    else:

        font = ImageFont.load_default()

    # Short thumbnail text.
    words = title.split()

    if len(words) > 6:
        words = words[:6]

    thumbnail_text = " ".join(
        words
    )

    bbox = draw.textbbox(
        (0, 0),
        thumbnail_text,
        font=font,
    )

    text_width = (
        bbox[2] -
        bbox[0]
    )

    x = (
        1280 -
        text_width
    ) // 2

    y = 530

    # Dark backing.
    padding = 22

    draw.rounded_rectangle(
        (
            x - padding,
            y - padding,
            x + text_width + padding,
            y + 100,
        ),
        radius=20,
        fill=(
            0,
            0,
            0,
            190,
        ),
    )

    draw.text(
        (
            x,
            y,
        ),
        thumbnail_text,
        font=font,
        fill="white",
        stroke_width=7,
        stroke_fill="black",
    )

    output = (
        THUMBNAIL_DIR /
        "mystery_thumbnail.jpg"
    )

    image.save(
        output,
        quality=95,
    )

    video.close()

    print(
        "✅ Thumbnail:",
        output,
    )

    return str(output)


# ============================================================
# FULL VIDEO
# ============================================================

def assemble_video(
    story
):

    print("\n" + "=" * 75)
    print("🎞️ BUILDING HIGH-RETENTION SHORT")
    print("=" * 75)

    scene_clips = []

    for scene in story["scenes"]:

        number = scene[
            "scene_number"
        ]

        query = scene[
            "pexels_query"
        ]

        narration = scene[
            "narration"
        ]

        caption = scene.get(
            "caption",
            "",
        )

        sfx = scene.get(
            "sfx"
        )

        print(
            f"\n🎥 SCENE {number}"
        )

        print(
            "Visual:",
            query
        )

        print(
            "Narration:",
            narration
        )

        # ----------------------------------------------------
        # Download video.
        # ----------------------------------------------------

        video_file = get_scene_video(
            number,
            query,
        )

        if not video_file:

            print(
                f"⚠️ Scene {number} "
                "could not be downloaded."
            )

            continue

        # ----------------------------------------------------
        # Voice.
        # ----------------------------------------------------

        audio_file = generate_voice(
            narration,
            number,
        )

        # ----------------------------------------------------
        # Build scene.
        # ----------------------------------------------------

        clip = build_scene(
            video_file,
            audio_file,
            caption,
            number,
            sfx,
        )

        scene_clips.append(
            clip
        )

    if not scene_clips:

        raise RuntimeError(
            "❌ No video scenes available."
        )

    print(
        "\n🔗 Joining all scenes..."
    )

    final_video = concatenate_videoclips(
        scene_clips,
        method="compose",
    )

    # --------------------------------------------------------
    # Add BGM.
    # --------------------------------------------------------

    final_video = add_background_music(
        final_video
    )

    # --------------------------------------------------------
    # Export.
    # --------------------------------------------------------

    output = (
        OUTPUT_DIR /
        "mystery_short.mp4"
    )

    print(
        "\n📤 Exporting:",
        output,
    )

    final_video.write_videofile(

        str(output),

        fps=FPS,

        codec="libx264",

        audio_codec="aac",

        preset="medium",

        bitrate="8M",

        pixel_format="yuv420p",

        threads=4,
    )

    duration = (
        final_video.duration
    )

    final_video.close()

    for clip in scene_clips:

        try:
            clip.close()
        except Exception:
            pass

    print(
        "\n🎉 VIDEO CREATED"
    )

    print(
        "⏱️ Duration:",
        round(duration, 2),
        "seconds",
    )

    print(
        "📁",
        output,
    )

    return str(output)


# ============================================================
# YOUTUBE AUTH
# ============================================================

def get_youtube_service():

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload"
    ]

    credentials = None

    # --------------------------------------------------------
    # Existing token.
    # --------------------------------------------------------

    if os.path.exists(
        TOKEN_FILE
    ):

        print(
            "🔐 Loading YouTube token..."
        )

        credentials = (
            Credentials.from_authorized_user_file(
                TOKEN_FILE,
                scopes,
            )
        )

    # --------------------------------------------------------
    # Local first-time login.
    # --------------------------------------------------------

    if (
        credentials is None
        or not credentials.valid
    ):

        if not os.path.exists(
            CLIENT_SECRET_FILE
        ):

            raise RuntimeError(
                "client_secret.json missing."
            )

        print(
            "🔑 Starting YouTube OAuth..."
        )

        flow = (
            InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE,
                scopes,
            )
        )

        credentials = (
            flow.run_local_server(
                port=0
            )
        )

        with open(
            TOKEN_FILE,
            "w",
            encoding="utf-8",
        ) as token:

            token.write(
                credentials.to_json()
            )

    return build(
        "youtube",
        "v3",
        credentials=credentials,
    )


# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def upload_to_youtube(
    video_path,
    title,
    description,
    thumbnail_path=None,
):

    print(
        "\n📤 UPLOADING TO YOUTUBE..."
    )

    youtube = get_youtube_service()

    final_title = title[:100]

    final_description = (
        description
        + "\n\n"
        + "#Shorts #IndianMystery #IndianHistory #IndiaFacts"
    )

    body = {

        "snippet": {

            "title":
                final_title,

            "description":
                final_description,

            "tags": [
                "Shorts",
                "Indian Mystery",
                "Indian History",
                "India Facts",
                "Indian Facts",
                "Dark History India",
                "Unsolved Indian Mystery",
                "Hindi Facts",
                "Hindi Mystery",
                "Indian Archaeology",
                "Ancient India",
                "Indian History Facts",
            ],

            "categoryId":
                "27",
        },

        "status": {

            "privacyStatus":
                "public",

            "selfDeclaredMadeForKids":
                False,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = request.execute()

    video_id = response.get(
        "id"
    )

    print(
        "\n🎉 YOUTUBE UPLOAD SUCCESS"
    )

    print(
        "🆔 Video ID:",
        video_id,
    )

    # --------------------------------------------------------
    # Thumbnail
    # --------------------------------------------------------

    if thumbnail_path and os.path.exists(
        thumbnail_path
    ):

        try:

            print(
                "🖼️ Uploading custom thumbnail..."
            )

            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    thumbnail_path,
                    mimetype="image/jpeg",
                ),
            ).execute()

            print(
                "✅ Thumbnail uploaded."
            )

        except Exception as e:

            print(
                "⚠️ Thumbnail upload failed:",
                e,
            )

    return video_id


# ============================================================
# CLEANUP OLD TEMP FILES
# ============================================================

def cleanup_old_scene_files():

    print(
        "\n🧹 Cleaning old temporary files..."
    )

    for folder in [
        CLIPS_DIR,
        AUDIO_DIR,
        CAPTION_DIR,
    ]:

        if not folder.exists():
            continue

        for item in folder.iterdir():

            try:

                if item.is_file():
                    item.unlink()

            except Exception:
                pass


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 75)
    print("🇮🇳 INDIA-ONLY DARK HISTORY & MYSTERY SHORTS AUTOBOT")
    print("=" * 75)
    print(
        "🎙️ Male Hindi Voice:",
        VOICE,
    )
    print(
        "⚡ Voice Speed:",
        VOICE_RATE,
    )
    print(
        "🎬 Format:",
        "1080x1920",
    )
    print(
        "📱 Shorts:",
        "9:16",
    )
    print(
        "✂️ Rapid Cuts:",
        "Enabled",
    )
    print(
        "💥 SFX:",
        "Enabled when files exist",
    )
    print(
        "📝 Captions:",
        "Enabled",
    )
    print(
        "🖼️ Thumbnail:",
        "Enabled",
    )
    print(
        "▶️ YouTube Upload:",
        "Enabled",
    )
    print(
        "🇮🇳 Niche:",
        "INDIA ONLY — Indian Facts / History / Mysteries",
    )
    print("=" * 75)

    cleanup_old_scene_files()

    # --------------------------------------------------------
    # Generate story.
    # --------------------------------------------------------

    story = generate_mystery_story()

    print("\n📜 GENERATED STORY:")
    print(
        json.dumps(
            story,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # Build video.
    # --------------------------------------------------------

    video_path = assemble_video(
        story
    )

    # --------------------------------------------------------
    # Thumbnail.
    # --------------------------------------------------------

    thumbnail = create_thumbnail(
        video_path,
        story.get(
            "title",
            "Mystery",
        ),
    )

    # --------------------------------------------------------
    # YouTube.
    # --------------------------------------------------------

    try:

        upload_to_youtube(
            video_path,
            story.get(
                "title",
                "Mystery Short #Shorts",
            ),
            story.get(
                "description",
                "",
            ),
            thumbnail,
        )

    except Exception as e:

        print(
            "\n⚠️ YouTube upload skipped/failed:"
        )

        print(e)

    print("\n" + "=" * 75)
    print("🎉 COMPLETE")
    print("=" * 75)

    print(
        "🎬 Video:",
        os.path.abspath(
            video_path
        ),
    )

    print(
        "🖼️ Thumbnail:",
        os.path.abspath(
            thumbnail
        ),
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print("\n" + "=" * 75)
        print("❌ FATAL ERROR")
        print("=" * 75)
        print(e)
        raise
