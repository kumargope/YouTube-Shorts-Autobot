import os
import json
import random
import asyncio
import requests
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
import edge_tts

# ============================================================
# MOVIEPY 2.x
# ============================================================

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    concatenate_audioclips,
)

import moviepy.video.fx as vfx

# ============================================================
# PIL
# ============================================================

from PIL import Image, ImageDraw, ImageFont

# ============================================================
# YOUTUBE API
# ============================================================

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
        "GROQ_API_KEY missing.\n"
        "Add GROQ_API_KEY=... to your .env file."
    )

if not PEXELS_API_KEY:
    raise ValueError(
        "PEXELS_API_KEY missing.\n"
        "Add PEXELS_API_KEY=... to your .env file."
    )

groq_client = Groq(
    api_key=GROQ_KEY
)

# ============================================================
# DIRECTORIES
# ============================================================

OUTPUT_DIR = Path("output")
CLIPS_DIR = OUTPUT_DIR / "clips"
AUDIO_DIR = OUTPUT_DIR / "audio"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CLIPS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# FILES
# ============================================================

BGM_FILE = "bgm.mp3"

CLIENT_SECRET_FILE = "client_secret.json"
YOUTUBE_TOKEN_FILE = "token.json"

# ============================================================
# VIDEO SETTINGS
# ============================================================

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

FPS = 30

# ============================================================
# MALE HINDI VOICE
# ============================================================

VOICE = "hi-IN-MadhurNeural"

# Faster but still understandable
VOICE_RATE = "+12%"

VOICE_PITCH = "-2Hz"

# ============================================================
# YOUTUBE SETTINGS
# ============================================================

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]

YOUTUBE_PRIVACY = os.getenv(
    "YOUTUBE_PRIVACY",
    "public"
)

# ============================================================
# MYSTERY TOPICS
# ============================================================

MYSTERY_TOPICS = [

    "Egyptian pyramids unsolved mystery",

    "Bermuda Triangle mystery",

    "Dyatlov Pass mystery",

    "Roanoke Colony disappearance",

    "Mary Celeste ghost ship",

    "Tutankhamun tomb mystery",

    "Nazca Lines mystery",

    "Antikythera mechanism mystery",

    "Voynich Manuscript mystery",

    "Oak Island treasure mystery",

    "Lost city of Atlantis",

    "Stonehenge mystery",

    "Terracotta Army mystery",

    "Jack the Ripper mystery",

    "Amelia Earhart disappearance",

    "D. B. Cooper disappearance",

    "Ghost ship mysteries",

    "Ancient Roman mysteries",

    "Pompeii mysteries",

    "Mohenjo-daro mystery",

    "Indian historical mysteries",

    "Ancient temple mysteries",

    "Unsolved historical disappearances",

    "Lost civilizations",

    "Ancient Egyptian tomb mysteries",

    "Medieval castle mysteries",

    "Ancient Indian mysteries",

    "Himalayan mysteries",

    "Abandoned ancient cities",

    "Unexplained archaeological discoveries",

]

# ============================================================
# USED TOPIC HISTORY
# ============================================================

HISTORY_FILE = Path(
    "used_topics.txt"
)


def load_used_topics():

    if not HISTORY_FILE.exists():
        return set()

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except Exception:

        return set()


def save_used_topic(topic):

    try:

        with open(
            HISTORY_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                topic.strip() + "\n"
            )

    except Exception as e:

        print(
            "⚠️ Could not save topic history:",
            e
        )


def choose_topic():

    used_topics = load_used_topics()

    available = [
        topic
        for topic in MYSTERY_TOPICS
        if topic not in used_topics
    ]

    if not available:

        print(
            "🔄 All topics used. "
            "Resetting topic rotation."
        )

        available = MYSTERY_TOPICS.copy()

    topic = random.choice(
        available
    )

    return topic


# ============================================================
# GROQ STORY GENERATOR
# ============================================================

def generate_mystery_story():

    topic = choose_topic()

    print("\n" + "=" * 70)
    print(
        "🧠 GENERATING DARK HISTORY / MYSTERY STORY"
    )
    print(
        "🎯 Topic:",
        topic
    )
    print("=" * 70)

    prompt = f"""
You are an expert YouTube Shorts storyteller
specializing in Dark History and Unsolved Mysteries.

TOPIC:
{topic}

Create ONE highly engaging Hindi YouTube Short.

TARGET LENGTH:
30-45 seconds.

VERY IMPORTANT:

The story should be based on real historical information
whenever possible.

Never present an uncertain theory as a confirmed fact.

Use wording such as:

"कुछ इतिहासकार मानते हैं..."
"एक सिद्धांत के अनुसार..."
"आज तक इसका निश्चित जवाब नहीं मिला..."
"रिकॉर्ड के अनुसार..."

RETENTION IS EXTREMELY IMPORTANT.

The first 2-4 seconds must immediately create curiosity.

The opening should:

- shock the viewer
- create a mystery
- create an unanswered question
- make the viewer want to know what happens next

Do NOT start with:

"आज हम बात करेंगे..."
"क्या आप जानते हैं..."
"नमस्कार दोस्तों..."

Start directly with the mystery.

The story should continuously reveal information.

Use short spoken sentences.

Avoid unnecessary explanations.

Create a curiosity chain:

HOOK
↓
MYSTERY
↓
CLUE
↓
MORE SUSPICION
↓
IMPORTANT REVELATION
↓
UNANSWERED QUESTION

FINAL ENDING:

The final line should be a powerful unanswered question
that makes the viewer think and potentially replay the video.

VISUAL REQUIREMENT:

This program uses REAL STOCK VIDEO FOOTAGE from Pexels.

Therefore every scene must have a realistic searchable
Pexels video query.

Do NOT create image prompts.

Do NOT ask for illustrations.

Do NOT use abstract concepts.

Example queries:

"ancient egypt pyramid night"

"desert pyramid archaeological site"

"ancient stone tunnel"

"archaeologist excavation"

"old ship ocean storm"

"ancient ruins aerial"

Each scene must visually match what is being narrated.

Create EXACTLY 5 scenes.

Target scene structure:

Scene 1:
0-4 seconds
VERY strong visual hook.

Scene 2:
4-11 seconds

Scene 3:
11-19 seconds

Scene 4:
19-29 seconds

Scene 5:
29-40+ seconds

The actual narration duration may slightly change
because of voice generation.

Each scene must contain:

scene_number
narration
pexels_query
caption

CAPTION:

Maximum 3-5 words.

Make it emotionally powerful.

TITLE:

Maximum approximately 50 characters.

Include relevant hashtags.

Example:

"पिरामिड का आखिरी रहस्य 😱 #Shorts"

DESCRIPTION:

Natural Hindi YouTube description.

Include relevant hashtags.

Do not use keyword stuffing.

Return ONLY valid JSON.

Required JSON:

{{
    "topic": "...",
    "title": "...",
    "description": "...",
    "scenes": [
        {{
            "scene_number": 1,
            "narration": "...",
            "pexels_query": "...",
            "caption": "..."
        }},
        {{
            "scene_number": 2,
            "narration": "...",
            "pexels_query": "...",
            "caption": "..."
        }},
        {{
            "scene_number": 3,
            "narration": "...",
            "pexels_query": "...",
            "caption": "..."
        }},
        {{
            "scene_number": 4,
            "narration": "...",
            "pexels_query": "...",
            "caption": "..."
        }},
        {{
            "scene_number": 5,
            "narration": "...",
            "pexels_query": "...",
            "caption": "..."
        }}
    ]
}}
"""

    response = groq_client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        messages=[

            {
                "role": "system",
                "content": (
                    "You are a factual, "
                    "high-retention Hindi "
                    "YouTube Shorts writer."
                )
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        temperature=0.85,

        response_format={
            "type": "json_object"
        }
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned empty response."
        )

    data = json.loads(
        content
    )

    # Validate scenes
    scenes = data.get(
        "scenes",
        []
    )

    if len(scenes) != 5:

        raise ValueError(
            f"Expected exactly 5 scenes, "
            f"got {len(scenes)}"
        )

    # Save topic
    save_used_topic(
        data.get(
            "topic",
            topic
        )
    )

    print("\n🎯 TITLE:")
    print(
        data.get(
            "title",
            "Mystery Short"
        )
    )

    return data


# ============================================================
# PEXELS VIDEO SEARCH
# ============================================================

def search_pexels_video(query):

    print(
        f"\n🔎 Pexels video search: {query}"
    )

    url = (
        "https://api.pexels.com/videos/search"
    )

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": query,
        "per_page": 20,
        "orientation": "portrait",
        "size": "large"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        if response.status_code != 200:

            print(
                "❌ Pexels error:",
                response.status_code
            )

            return None

        data = response.json()

        videos = data.get(
            "videos",
            []
        )

        # ----------------------------------------------------
        # LANDSCAPE FALLBACK
        # ----------------------------------------------------

        if not videos:

            print(
                "⚠️ No portrait footage."
            )

            print(
                "🔄 Trying landscape..."
            )

            params["orientation"] = "landscape"

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                return None

            data = response.json()

            videos = data.get(
                "videos",
                []
            )

        if not videos:
            return None

        candidates = []

        for video in videos:

            files = video.get(
                "video_files",
                []
            )

            for file in files:

                width = (
                    file.get("width")
                    or 0
                )

                height = (
                    file.get("height")
                    or 0
                )

                link = file.get(
                    "link"
                )

                if not link:
                    continue

                if width >= 720 and height >= 720:

                    candidates.append({

                        "url": link,

                        "width": width,

                        "height": height,

                        "duration": (
                            video.get(
                                "duration",
                                0
                            )
                        )
                    })

        if not candidates:
            return None

        # Prefer portrait
        vertical = [

            item

            for item in candidates

            if item["height"] >
               item["width"]

        ]

        if vertical:

            candidates = vertical

        # Prefer larger resolution
        candidates.sort(
            key=lambda x:
            x["width"] * x["height"],
            reverse=True
        )

        # Select among best candidates
        best_count = min(
            5,
            len(candidates)
        )

        selected = random.choice(
            candidates[:best_count]
        )

        print(
            "✅ Selected:",
            f"{selected['width']}x"
            f"{selected['height']}"
        )

        return selected

    except Exception as e:

        print(
            "❌ Pexels request failed:",
            e
        )

        return None


# ============================================================
# DOWNLOAD VIDEO
# ============================================================

def download_video(
    url,
    filename
):

    print(
        f"⬇️ Downloading {filename}"
    )

    path = CLIPS_DIR / filename

    try:

        response = requests.get(
            url,
            stream=True,
            timeout=120
        )

        if response.status_code != 200:

            print(
                "❌ Download failed:",
                response.status_code
            )

            return None

        with open(
            path,
            "wb"
        ) as f:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:

                    f.write(
                        chunk
                    )

        print(
            "✅ Saved:",
            path
        )

        return str(path)

    except Exception as e:

        print(
            "❌ Video download error:",
            e
        )

        return None


# ============================================================
# GET SCENE VIDEO
# ============================================================

def get_scene_video(
    scene_number,
    query
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
        filename
    )


# ============================================================
# MALE HINDI VOICE
# ============================================================

async def create_voice(
    text,
    output_file
):

    print(
        "🎙️ Voice speed:",
        VOICE_RATE
    )

    communicate = edge_tts.Communicate(

        text=text,

        voice=VOICE,

        rate=VOICE_RATE,

        pitch=VOICE_PITCH
    )

    await communicate.save(
        output_file
    )


def generate_voice(
    text,
    scene_number
):

    filename = (
        AUDIO_DIR /
        f"voice_{scene_number}.mp3"
    )

    print(
        f"🎙️ Generating male Hindi voice "
        f"for scene {scene_number}"
    )

    asyncio.run(
        create_voice(
            text,
            str(filename)
        )
    )

    return str(filename)


# ============================================================
# PREPARE SHORTS VIDEO
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

    # --------------------------------------------------------
    # Landscape / wide
    # --------------------------------------------------------

    if current_ratio > target_ratio:

        new_width = int(
            height *
            target_ratio
        )

        x1 = int(
            (width - new_width) / 2
        )

        clip = clip.cropped(

            x1=x1,

            x2=x1 + new_width
        )

    # --------------------------------------------------------
    # Tall
    # --------------------------------------------------------

    else:

        new_height = int(
            width /
            target_ratio
        )

        y1 = int(
            (height - new_height) / 2
        )

        clip = clip.cropped(

            y1=y1,

            y2=y1 + new_height
        )

    clip = clip.resized(

        width=VIDEO_WIDTH,

        height=VIDEO_HEIGHT
    )

    return clip


# ============================================================
# FONT
# ============================================================

def find_font():

    possible_fonts = [

        "C:/Windows/Fonts/NirmalaB.ttf",

        "C:/Windows/Fonts/mangal.ttf",

        "C:/Windows/Fonts/arialbd.ttf",

        "C:/Windows/Fonts/segoeuib.ttf",

    ]

    for font in possible_fonts:

        if os.path.exists(font):

            return font

    return None


# ============================================================
# CAPTION IMAGE
# ============================================================

def create_caption_image(
    text,
    filename
):

    image = Image.new(
        "RGBA",
        (
            VIDEO_WIDTH,
            360
        ),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        image
    )

    font_path = find_font()

    if font_path:

        font = ImageFont.truetype(
            font_path,
            68
        )

    else:

        font = ImageFont.load_default()

    words = text.split()

    lines = []

    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

        if len(test) > 24:

            if current:
                lines.append(
                    current
                )

            current = word

        else:

            current = test

    if current:

        lines.append(
            current
        )

    lines = lines[:2]

    y = 65

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        text_width = (
            bbox[2] -
            bbox[0]
        )

        x = (
            VIDEO_WIDTH -
            text_width
        ) // 2

        # Strong black outline
        draw.text(

            (x, y),

            line,

            font=font,

            fill="white",

            stroke_width=9,

            stroke_fill="black"
        )

        y += 90

    image.save(
        filename
    )

    return filename


# ============================================================
# BUILD SINGLE SCENE
# ============================================================

def build_scene(
    video_path,
    audio_path,
    caption,
    scene_number
):

    print(
        f"\n🎬 Building scene {scene_number}"
    )

    audio = AudioFileClip(
        audio_path
    )

    duration = audio.duration

    video = VideoFileClip(
        video_path
    )

    print(
        f"🎙️ Narration duration: "
        f"{duration:.2f}s"
    )

    print(
        f"🎥 Source video duration: "
        f"{video.duration:.2f}s"
    )

    # --------------------------------------------------------
    # LOOP SHORT FOOTAGE
    # --------------------------------------------------------

    if video.duration < duration:

        loops = (
            int(
                duration /
                video.duration
            )
            + 1
        )

        print(
            f"🔁 Looping footage "
            f"{loops} times"
        )

        pieces = []

        for _ in range(loops):

            pieces.append(
                video.subclipped(
                    0,
                    video.duration
                )
            )

        video = concatenate_videoclips(
            pieces,
            method="compose"
        )

    # --------------------------------------------------------
    # EXACT AUDIO DURATION
    # --------------------------------------------------------

    video = video.subclipped(
        0,
        duration
    )

    # --------------------------------------------------------
    # 9:16 SHORTS
    # --------------------------------------------------------

    video = prepare_clip_for_shorts(
        video
    )

    # --------------------------------------------------------
    # AUDIO
    # --------------------------------------------------------

    video = video.with_audio(
        audio
    )

    # --------------------------------------------------------
    # SMALL CROSSFADE
    # --------------------------------------------------------

    try:

        video = video.with_effects(
            [
                vfx.CrossFadeIn(
                    0.10
                )
            ]
        )

    except Exception:
        pass

    return video


# ============================================================
# BUILD COMPLETE VIDEO
# ============================================================

def assemble_video(
    story
):

    print("\n" + "=" * 70)
    print(
        "🎞️ BUILDING REAL VIDEO SHORT"
    )
    print("=" * 70)

    scene_clips = []

    scenes = story.get(
        "scenes",
        []
    )

    for scene in scenes:

        number = scene[
            "scene_number"
        ]

        query = scene[
            "pexels_query"
        ]

        caption = scene.get(
            "caption",
            ""
        )

        print(
            f"\n🎥 SCENE {number}"
        )

        print(
            "🔎 Search:",
            query
        )

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        video_file = get_scene_video(
            number,
            query
        )

        if not video_file:

            print(
                f"⚠️ Scene {number} "
                "has no footage."
            )

            continue

        # ----------------------------------------------------
        # VOICE
        # ----------------------------------------------------

        audio_file = generate_voice(
            scene["narration"],
            number
        )

        # ----------------------------------------------------
        # BUILD SCENE
        # ----------------------------------------------------

        clip = build_scene(

            video_file,

            audio_file,

            caption,

            number
        )

        scene_clips.append(
            clip
        )

    if not scene_clips:

        raise RuntimeError(
            "❌ No Pexels video clips "
            "were successfully created."
        )

    # ========================================================
    # JOIN
    # ========================================================

    print(
        "\n🔗 Joining scenes..."
    )

    final_video = concatenate_videoclips(

        scene_clips,

        method="compose"
    )

    # ========================================================
    # BACKGROUND MUSIC
    # ========================================================

    if os.path.exists(
        BGM_FILE
    ):

        print(
            "🎵 Adding suspense "
            "background music..."
        )

        bgm = AudioFileClip(
            BGM_FILE
        )

        # ----------------------------------------------------
        # LOOP BGM
        # ----------------------------------------------------

        if bgm.duration < final_video.duration:

            loops = (
                int(
                    final_video.duration /
                    bgm.duration
                )
                + 1
            )

            bgm_parts = []

            for _ in range(loops):

                bgm_parts.append(
                    bgm.subclipped(
                        0,
                        bgm.duration
                    )
                )

            bgm = concatenate_audioclips(
                bgm_parts
            )

        # ----------------------------------------------------
        # EXACT LENGTH
        # ----------------------------------------------------

        bgm = bgm.subclipped(
            0,
            final_video.duration
        )

        # ----------------------------------------------------
        # LOW MUSIC VOLUME
        # ----------------------------------------------------

        bgm = bgm.with_volume_scaled(
            0.055
        )

        # ----------------------------------------------------
        # MIX VOICE + MUSIC
        # ----------------------------------------------------

        if final_video.audio:

            final_audio = CompositeAudioClip(

                [
                    final_video.audio,
                    bgm
                ]

            )

        else:

            final_audio = bgm

        final_video = final_video.with_audio(
            final_audio
        )

    else:

        print(
            "⚠️ bgm.mp3 not found."
        )

        print(
            "Continuing with voice only."
        )

    # ========================================================
    # EXPORT
    # ========================================================

    output = (
        OUTPUT_DIR /
        "mystery_short.mp4"
    )

    print(
        "\n📤 Exporting:"
    )

    print(
        output
    )

    final_video.write_videofile(

        str(output),

        fps=FPS,

        codec="libx264",

        audio_codec="aac",

        preset="medium",

        bitrate="8M",

        pixel_format="yuv420p",

        threads=4
    )

    # ========================================================
    # CLEANUP
    # ========================================================

    try:

        final_video.close()

    except Exception:
        pass

    for clip in scene_clips:

        try:
            clip.close()

        except Exception:
            pass

    print("\n" + "=" * 70)
    print(
        "🎉 VIDEO CREATED SUCCESSFULLY"
    )
    print(
        "📁",
        output
    )
    print("=" * 70)

    return str(output)


# ============================================================
# YOUTUBE AUTHENTICATION
# ============================================================

def get_youtube_credentials():

    client_secret = Path(
        CLIENT_SECRET_FILE
    )

    token_file = Path(
        YOUTUBE_TOKEN_FILE
    )

    if not client_secret.exists():

        print(
            "\n⚠️ client_secret.json "
            "not found."
        )

        print(
            "YouTube upload skipped."
        )

        return None

    credentials = None

    # --------------------------------------------------------
    # EXISTING TOKEN
    # --------------------------------------------------------

    if token_file.exists():

        try:

            credentials = (
                Credentials
                .from_authorized_user_file(
                    str(token_file),
                    YOUTUBE_SCOPES
                )
            )

        except Exception as e:

            print(
                "⚠️ Existing YouTube "
                "token invalid:",
                e
            )

            credentials = None

    # --------------------------------------------------------
    # REFRESH TOKEN
    # --------------------------------------------------------

    if credentials:

        if credentials.valid:

            return credentials

        if (
            credentials.expired
            and
            credentials.refresh_token
        ):

            try:

                from google.auth.transport.requests import (
                    Request
                )

                credentials.refresh(
                    Request()
                )

                with open(
                    token_file,
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(
                        credentials.to_json()
                    )

                print(
                    "✅ YouTube token refreshed."
                )

                return credentials

            except Exception as e:

                print(
                    "⚠️ Token refresh failed:",
                    e
                )

                credentials = None

    # --------------------------------------------------------
    # FIRST TIME LOGIN
    # --------------------------------------------------------

    print(
        "\n🌐 Starting YouTube OAuth..."
    )

    flow = (
        InstalledAppFlow
        .from_client_secrets_file(
            str(client_secret),
            YOUTUBE_SCOPES
        )
    )

    credentials = (
        flow.run_local_server(
            port=0
        )
    )

    with open(
        token_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            credentials.to_json()
        )

    print(
        "✅ YouTube authorization complete."
    )

    return credentials


# ============================================================
# YOUTUBE AUTO UPLOAD
# ============================================================

def upload_to_youtube(
    video_path,
    title,
    description
):

    print("\n" + "=" * 70)
    print(
        "📤 UPLOADING VIDEO TO YOUTUBE"
    )
    print("=" * 70)

    credentials = (
        get_youtube_credentials()
    )

    if not credentials:

        return None

    try:

        youtube = build(

            "youtube",

            "v3",

            credentials=credentials
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        clean_title = str(
            title
        ).strip()

        if len(clean_title) > 100:

            clean_title = (
                clean_title[:97]
                + "..."
            )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        clean_description = (
            str(description)
            .strip()
        )

        upload_description = (
            clean_description
            +
            "\n\n"
            "#Shorts "
            "#Mystery "
            "#History "
            "#DarkHistory "
            "#UnsolvedMystery"
        )

        # ----------------------------------------------------
        # YOUTUBE BODY
        # ----------------------------------------------------

        body = {

            "snippet": {

                "title":
                    clean_title,

                "description":
                    upload_description,

                "tags": [

                    "Shorts",

                    "Mystery",

                    "History",

                    "Dark History",

                    "Unsolved Mystery",

                    "Hindi Mystery",

                    "Historical Mystery",

                    "Mystery Shorts",

                    "Hindi Shorts"

                ],

                "categoryId":
                    "24"
            },

            "status": {

                "privacyStatus":
                    YOUTUBE_PRIVACY,

                "selfDeclaredMadeForKids":
                    False
            }
        }

        # ----------------------------------------------------
        # MEDIA
        # ----------------------------------------------------

        media = MediaFileUpload(

            video_path,

            mimetype="video/mp4",

            chunksize=
                8 * 1024 * 1024,

            resumable=True
        )

        request = youtube.videos().insert(

            part="snippet,status",

            body=body,

            media_body=media
        )

        response = None

        # ----------------------------------------------------
        # UPLOAD LOOP
        # ----------------------------------------------------

        while response is None:

            try:

                status, response = (
                    request.next_chunk()
                )

                if status:

                    progress = int(

                        status.progress()
                        * 100

                    )

                    print(
                        f"📤 Upload: "
                        f"{progress}%"
                    )

            except Exception as e:

                print(
                    "\n❌ YouTube upload error:"
                )

                print(e)

                return None

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        video_id = response.get(
            "id"
        )

        print("\n" + "=" * 70)
        print(
            "🎉 YOUTUBE UPLOAD SUCCESS"
        )
        print("=" * 70)

        print(
            "🆔 Video ID:",
            video_id
        )

        if video_id:

            print(
                "🔗 https://www.youtube.com/watch?v="
                + video_id
            )

        print(
            "🔐 Privacy:",
            YOUTUBE_PRIVACY
        )

        print("=" * 70)

        return video_id

    except Exception as e:

        print(
            "\n❌ YouTube API error:"
        )

        print(e)

        return None


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("\n")
    print("=" * 70)
    print(
        "🚀 DARK HISTORY YOUTUBE SHORTS BOT"
    )
    print("=" * 70)
    print(
        "🎙️ Voice:",
        VOICE
    )
    print(
        "⚡ Voice speed:",
        VOICE_RATE
    )
    print(
        "🎥 Source: Pexels REAL VIDEO"
    )
    print(
        "📱 Format: 1080x1920"
    )
    print(
        "📤 YouTube upload:",
        YOUTUBE_PRIVACY
    )
    print("=" * 70)

    try:

        # ====================================================
        # STEP 1
        # ====================================================

        story = generate_mystery_story()

        print(
            "\n📜 STORY GENERATED"
        )

        print(
            json.dumps(
                story,
                ensure_ascii=False,
                indent=2
            )
        )

        # ====================================================
        # STEP 2
        # ====================================================

        video = assemble_video(
            story
        )

        print(
            "\n✅ FINAL VIDEO:"
        )

        print(
            os.path.abspath(
                video
            )
        )

        # ====================================================
        # STEP 3
        # ====================================================

        print(
            "\n📤 Starting YouTube upload..."
        )

        video_id = upload_to_youtube(

            video_path=video,

            title=story.get(
                "title",
                "Mystery Short"
            ),

            description=story.get(
                "description",
                ""
            )
        )

        # ====================================================
        # FINAL STATUS
        # ====================================================

        print("\n" + "=" * 70)

        if video_id:

            print(
                "🎉 COMPLETE!"
            )

            print(
                "🎬 Video generated"
            )

            print(
                "📤 Video uploaded"
            )

            print(
                "🆔 YouTube ID:",
                video_id
            )

            print(
                "🔗 https://www.youtube.com/watch?v="
                + video_id
            )

        else:

            print(
                "✅ VIDEO CREATED"
            )

            print(
                "⚠️ YouTube upload skipped/failed."
            )

            print(
                "📁 Local video:"
            )

            print(
                os.path.abspath(
                    video
                )
            )

        print("=" * 70)

    except KeyboardInterrupt:

        print(
            "\n🛑 Program stopped by user."
        )

    except Exception as e:

        print(
            "\n❌ PROGRAM ERROR:"
        )

        print(
            repr(e)
        )

        print(
            "\nCheck the error above."
        )

        raise