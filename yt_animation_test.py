import os
import json
import random
import asyncio
import math
import time
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from groq import Groq
import edge_tts

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    concatenate_videoclips,
    concatenate_audioclips,
)
import moviepy.video.fx as vfx

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not GROQ_KEY:
    raise ValueError("GROQ_API_KEY missing.")

if not PEXELS_API_KEY:
    raise ValueError("PEXELS_API_KEY missing.")

groq_client = Groq(api_key=GROQ_KEY)

OUTPUT_DIR = Path("output")
CLIPS_DIR = OUTPUT_DIR / "clips"
AUDIO_DIR = OUTPUT_DIR / "audio"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"
SFX_DIR = Path("sfx")

for folder in (
    OUTPUT_DIR,
    CLIPS_DIR,
    AUDIO_DIR,
    THUMBNAIL_DIR,
    SFX_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)

BGM_FILE = Path("bgm.mp3")

WHOOSH_FILE = SFX_DIR / "whoosh.mp3"
IMPACT_FILE = SFX_DIR / "impact.mp3"
HEARTBEAT_FILE = SFX_DIR / "heartbeat.mp3"
HIT_FILE = SFX_DIR / "hit.mp3"

TOKEN_FILE = Path("token.json")
CLIENT_SECRET_FILE = Path("client_secret.json")

USED_TOPICS_FILE = Path("used_topics.json")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = "+16%"
VOICE_PITCH = "-2Hz"

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"

MAX_SHORT_DURATION = 35.0

YOUTUBE_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
YOUTUBE_UPLOAD_MAX_RETRIES = 6

GITHUB_TOKEN_SECRET_NAMES = (
    "YOUTUBE_TOKEN_JSON",
    "TOKEN_JSON",
)

# ------------------------------------------------------------
# RETRY SETTINGS
# ------------------------------------------------------------

# पूरे video को दोबारा generate करने की maximum कोशिश।
MAX_FULL_VIDEO_ATTEMPTS = 4

# हर scene के लिए Pexels queries की maximum संख्या।
MAX_PEXELS_QUERY_ATTEMPTS = 8

# SFX volume.
# पहले 0.28 था।
# अब काफी stronger रखा गया है।
SFX_BASE_VOLUME = 0.72

# BGM voice/SFX को दबाए नहीं।
BGM_VOLUME = 0.24

# SFX को scene में maximum कितनी देर तक रखें।
MAX_SFX_DURATION = 1.25


# ============================================================
# INDIA-ONLY MYSTERY TOPICS
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
    "Kailasa Temple Ellora construction mystery",
    "Iron Pillar Delhi rust mystery",
    "Delhi Sultanate forgotten history",
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
    "Subhas Chandra Bose historical mystery",
    "Lal Bahadur Shastri historical mystery",
    "Indian ancient manuscript mystery",
    "Indian archaeological discovery mystery",
    "Indian temple underground tunnel mystery",
    "Indian lost city historical mystery",
    "Indian shipwreck historical mystery",
    "Indian haunted fort folklore mystery",
    "Indian cave civilization mystery",
    "Indian ancient engineering mystery",
    "Indian astronomy ancient history mystery",
    "Indian stepwell hidden history",
    "Indian railway historical mystery",
    "Indian historical artifact mystery",
]


# ============================================================
# INDIA VALIDATION
# ============================================================

FORBIDDEN_FOREIGN_TERMS = [
    "bermuda",
    "dyatlov",
    "roanoke",
    "mary celeste",
    "tutankhamun",
    "egypt",
    "egyptian",
    "nazca",
    "antikythera",
    "voynich",
    "oak island",
    "atlantis",
    "stonehenge",
    "jack the ripper",
    "amelia earhart",
    "d.b. cooper",
    "pompeii",
    "roman empire",
    "viking",
    "europe",
    "america",
    "new york",
    "london",
    "paris",
    "japan",
    "china",
    "greece",
    "mesopotamia",
]

INDIA_TERMS = [
    "india",
    "indian",
    "भारत",
    "भारतीय",
    "rajasthan",
    "delhi",
    "uttarakhand",
    "odisha",
    "karnataka",
    "kerala",
    "tamil nadu",
    "tamil",
    "andhra",
    "telangana",
    "maharashtra",
    "gujarat",
    "bihar",
    "madhya pradesh",
    "west bengal",
    "punjab",
    "assam",
    "goa",
    "hampi",
    "varanasi",
    "jaipur",
    "agra",
    "hyderabad",
    "mumbai",
    "kolkata",
    "chennai",
    "puri",
    "konark",
]


def ensure_india_query(query):
    query = str(query or "").strip()

    if not query:
        query = "Indian history"

    lowered = query.lower()

    if any(
        term in lowered
        for term in FORBIDDEN_FOREIGN_TERMS
    ):
        raise ValueError(
            f"Non-Indian visual query rejected: {query}"
        )

    if not any(
        term in lowered
        for term in INDIA_TERMS
    ):
        query = f"India {query}"

    return query


# ============================================================
# USED TOPIC TRACKING
# ============================================================

def normalize_topic(topic):
    return " ".join(
        str(topic or "").strip().lower().split()
    )


def load_used_topics():

    if not USED_TOPICS_FILE.exists():
        return set()

    try:
        with open(
            USED_TOPICS_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            topics = data.get("topics", [])

        elif isinstance(data, list):
            topics = data

        else:
            topics = []

        return {
            normalize_topic(topic)
            for topic in topics
            if str(topic).strip()
        }

    except Exception as e:

        print(
            "⚠️ Could not read used_topics.json:",
            e,
        )

        return set()


def save_used_topics(used_topics):

    normalized = sorted(
        {
            normalize_topic(topic)
            for topic in used_topics
            if str(topic).strip()
        }
    )

    temp_file = USED_TOPICS_FILE.with_suffix(".tmp")

    data = {
        "topics": normalized,
        "updated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temp_file.replace(
            USED_TOPICS_FILE
        )

    except Exception as e:

        print(
            "⚠️ Could not save used_topics.json:",
            e,
        )


def mark_topic_used(topic):

    used_topics = load_used_topics()

    used_topics.add(
        normalize_topic(topic)
    )

    save_used_topics(
        used_topics
    )

    print(
        f"💾 Topic saved to {USED_TOPICS_FILE}: {topic}"
    )


def choose_unused_topic():

    used_topics = load_used_topics()

    available = [
        topic
        for topic in MYSTERY_TOPICS
        if normalize_topic(topic)
        not in used_topics
    ]

    print(
        f"📚 Topic history: "
        f"{len(used_topics)} used / "
        f"{len(MYSTERY_TOPICS)} total"
    )

    if not available:

        raise RuntimeError(
            "\n❌ ALL INDIA MYSTERY TOPICS HAVE ALREADY BEEN USED.\n"
            "No duplicate topic will be generated.\n"
            f"Edit {USED_TOPICS_FILE} only if you intentionally "
            "want to reset the topic history."
        )

    topic = random.choice(
        available
    )

    print(
        f"🆕 Unused topic selected: {topic}"
    )

    return topic


# ============================================================
# STORY VALIDATION
# ============================================================

def validate_indian_story(
    data,
    expected_topic=None,
):

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "AI response is not a JSON object."
        )

    text_parts = [
        str(data.get("topic", "")),
        str(data.get("title", "")),
        str(data.get("description", "")),
        str(data.get("hook", "")),
    ]

    scenes = data.get(
        "scenes",
        [],
    )

    if not isinstance(
        scenes,
        list,
    ):
        raise ValueError(
            "AI response contains invalid scenes."
        )

    for scene in scenes:

        if isinstance(
            scene,
            dict,
        ):

            text_parts.extend(
                [
                    str(
                        scene.get(
                            "narration",
                            "",
                        )
                    ),
                    str(
                        scene.get(
                            "pexels_query",
                            "",
                        )
                    ),
                    str(
                        scene.get(
                            "sfx_reason",
                            "",
                        )
                    ),
                ]
            )

    combined = " ".join(
        text_parts
    ).lower()

    if any(
        term in combined
        for term in FORBIDDEN_FOREIGN_TERMS
    ):

        raise ValueError(
            "Generated story contains a forbidden foreign topic."
        )

    expected_topic_text = str(
        expected_topic
        or data.get(
            "topic",
            "",
        )
    ).lower()

    topic_is_known_indian = any(
        expected_topic_text.strip().lower()
        == str(topic).strip().lower()
        for topic in MYSTERY_TOPICS
    )

    story_mentions_india = any(
        term in combined
        for term in INDIA_TERMS
    )

    if not (
        topic_is_known_indian
        or story_mentions_india
    ):

        raise ValueError(
            "Generated story does not clearly identify India."
        )

    if len(scenes) != 7:

        raise ValueError(
            f"Expected exactly 7 scenes, got {len(scenes)}"
        )

    for scene in scenes:

        if not isinstance(
            scene,
            dict,
        ):

            raise ValueError(
                "Invalid scene object."
            )

        scene[
            "pexels_query"
        ] = ensure_india_query(
            scene.get(
                "pexels_query",
                "",
            )
        )

        # ----------------------------------------------------
        # Normalize SFX information.
        # ----------------------------------------------------

        raw_sfx = scene.get(
            "sfx",
            None,
        )

        if isinstance(
            raw_sfx,
            str,
        ):

            raw_sfx = raw_sfx.lower().strip()

            if raw_sfx not in {
                "whoosh",
                "impact",
                "heartbeat",
                "hit",
            }:

                raw_sfx = None

        else:

            raw_sfx = None

        if not raw_sfx:

            raw_sfx = choose_sfx_from_story(
                scene.get(
                    "narration",
                    "",
                ),
                scene.get(
                    "sfx_reason",
                    "",
                ),
                scene.get(
                    "emotion",
                    "",
                ),
                scene.get(
                    "reaction",
                    "",
                ),
                scene.get(
                    "scene_purpose",
                    "",
                ),
            )

        scene["sfx"] = raw_sfx

    if expected_topic:

        data["topic"] = expected_topic

    return data


# ============================================================
# SFX INTELLIGENCE
# ============================================================

SFX_NAMES = {
    "whoosh",
    "impact",
    "heartbeat",
    "hit",
}


def choose_sfx_from_story(
    narration,
    reason="",
    emotion="",
    reaction="",
    scene_purpose="",
):

    text = " ".join(
        [
            str(narration or ""),
            str(reason or ""),
            str(emotion or ""),
            str(reaction or ""),
            str(scene_purpose or ""),
        ]
    ).lower()

    # --------------------------------------------------------
    # Strong shock / revelation.
    # --------------------------------------------------------

    impact_words = [
        "खुलासा",
        "सच सामने",
        "सच्चाई सामने",
        "चौंकाने",
        "चौंका",
        "हैरान",
        "सबसे बड़ा",
        "बड़ा राज",
        "राज खुल",
        "रहस्य खुल",
        "सदियों बाद",
        "पता चला",
        "खोज",
        "मिला",
        "मिल गया",
        "reveal",
        "revealed",
        "shocking",
        "shock",
        "revelation",
        "discovered",
        "discovery",
        "truth",
    ]

    if any(
        word in text
        for word in impact_words
    ):
        return "impact"

    # --------------------------------------------------------
    # Sudden event / punch.
    # --------------------------------------------------------

    hit_words = [
        "अचानक",
        "तुरंत",
        "धमाका",
        "टक्कर",
        "वार",
        "गिरा",
        "गिर गया",
        "टूट",
        "हमला",
        "खतरा",
        "संकट",
        "मौत",
        "मर गया",
        "डरावना",
        "भयानक",
        "suddenly",
        "sudden",
        "attack",
        "danger",
        "death",
        "dead",
        "hit",
        "crash",
        "break",
    ]

    if any(
        word in text
        for word in hit_words
    ):
        return "hit"

    # --------------------------------------------------------
    # Fear / suspense / unknown.
    # --------------------------------------------------------

    heartbeat_words = [
        "डर",
        "डरावना",
        "सस्पेंस",
        "रहस्य",
        "अज्ञात",
        "अनसुलझा",
        "जवाब नहीं",
        "पता नहीं",
        "आज तक",
        "क्यों",
        "कैसे",
        "रात",
        "अंधेरा",
        "सन्नाटा",
        "भूत",
        "खौफ",
        "सिद्धांत",
        "folklore",
        "mystery",
        "mysterious",
        "unknown",
        "unexplained",
        "suspense",
        "fear",
        "scary",
        "night",
    ]

    if any(
        word in text
        for word in heartbeat_words
    ):
        return "heartbeat"

    # --------------------------------------------------------
    # Movement / transition / reveal entrance.
    # --------------------------------------------------------

    whoosh_words = [
        "फिर",
        "इसके बाद",
        "अगला सुराग",
        "सुराग",
        "रास्ता",
        "दरवाजा",
        "सुरंग",
        "अंदर",
        "ऊपर",
        "नीचे",
        "तेजी",
        "चलते",
        "दिखाई",
        "सामने आया",
        "transition",
        "move",
        "moving",
        "entrance",
        "tunnel",
        "door",
        "clue",
    ]

    if any(
        word in text
        for word in whoosh_words
    ):
        return "whoosh"

    # --------------------------------------------------------
    # Intelligent fallback.
    # --------------------------------------------------------

    return random.choice(
        [
            "heartbeat",
            "whoosh",
            "impact",
            "hit",
        ]
    )


def get_sfx_intensity(
    sfx_name,
    narration,
    reason="",
    emotion="",
    reaction="",
):

    text = " ".join(
        [
            str(narration or ""),
            str(reason or ""),
            str(emotion or ""),
            str(reaction or ""),
        ]
    ).lower()

    intensity = 1.0

    if sfx_name == "heartbeat":
        intensity = 0.78

    elif sfx_name == "whoosh":
        intensity = 0.92

    elif sfx_name == "impact":
        intensity = 1.15

    elif sfx_name == "hit":
        intensity = 1.05

    # Extra emphasis for shock/reveal.
    strong_words = [
        "खुलासा",
        "चौंक",
        "सच",
        "सबसे बड़ा",
        "अचानक",
        "रहस्य",
        "मौत",
        "खतरा",
        "reveal",
        "shock",
        "sudden",
        "truth",
        "danger",
    ]

    if any(
        word in text
        for word in strong_words
    ):
        intensity *= 1.08

    return max(
        0.55,
        min(
            1.25,
            intensity,
        ),
    )


# ============================================================
# SEO GENERATOR
# ============================================================

def clean_hashtag(value):

    value = str(
        value or ""
    ).strip()

    if not value:
        return ""

    value = value.replace(
        "#",
        "",
    )

    value = "".join(
        char
        for char in value
        if char.isalnum()
        or char in "_"
    )

    return (
        f"#{value}"
        if value
        else ""
    )


def normalize_seo(
    data,
    topic,
):

    seo = data.get(
        "seo"
    )

    if not isinstance(
        seo,
        dict,
    ):
        seo = {}

    title = str(
        seo.get(
            "title"
        )
        or data.get(
            "title"
        )
        or f"{topic} | Indian Mystery #Shorts"
    ).strip()

    description = str(
        seo.get(
            "description"
        )
        or data.get(
            "description"
        )
        or ""
    ).strip()

    tags = seo.get(
        "tags",
        [],
    )

    if not isinstance(
        tags,
        list,
    ):
        tags = []

    hashtags = seo.get(
        "hashtags",
        [],
    )

    if not isinstance(
        hashtags,
        list,
    ):
        hashtags = []

    clean_tags = []

    for tag in tags:

        tag = str(
            tag
        ).strip()

        if (
            tag
            and tag.lower()
            not in {
                x.lower()
                for x in clean_tags
            }
        ):

            clean_tags.append(
                tag
            )

    clean_hashtags = []

    for hashtag in hashtags:

        hashtag = clean_hashtag(
            hashtag
        )

        if (
            hashtag
            and hashtag.lower()
            not in {
                x.lower()
                for x in clean_hashtags
            }
        ):

            clean_hashtags.append(
                hashtag
            )

    fallback_tags = [
        "Indian Mystery",
        "Indian History",
        "India Facts",
        "Hindi Mystery",
        "Hindi Facts",
        "Indian History Facts",
        topic,
    ]

    for tag in fallback_tags:

        if (
            tag.lower()
            not in {
                x.lower()
                for x in clean_tags
            }
        ):

            clean_tags.append(
                tag
            )

    fallback_hashtags = [
        "#Shorts",
        "#IndianMystery",
        "#IndianHistory",
        "#IndiaFacts",
    ]

    for hashtag in fallback_hashtags:

        if (
            hashtag.lower()
            not in {
                x.lower()
                for x in clean_hashtags
            }
        ):

            clean_hashtags.append(
                hashtag
            )

    clean_tags = clean_tags[:30]

    hashtag_text = " ".join(
        clean_hashtags[:12]
    )

    if hashtag_text:

        if hashtag_text.lower() not in description.lower():

            description = (
                description.rstrip()
                + "\n\n"
                + hashtag_text
            )

    title = title[:100]

    data["seo"] = {
        "title": title,
        "description": description,
        "tags": clean_tags,
        "hashtags": clean_hashtags,
    }

    data["title"] = title
    data["description"] = description

    return data


# ============================================================
# STORY GENERATOR
# ============================================================

def generate_mystery_story():

    topic = choose_unused_topic()

    print("\n" + "=" * 75)
    print(
        "🧠 GENERATING HIGH-RETENTION MYSTERY SHORT"
    )
    print(
        "🎯 Topic:",
        topic,
    )
    print("=" * 75)

    prompt = f"""
You are a professional Hindi YouTube Shorts writer,
Indian dark-history researcher and SEO specialist.

INDIA ONLY.

SELECTED TOPIC:
{topic}

Create ONE factual, highly engaging Hindi YouTube Short.

TARGET:
20-32 seconds.
Exactly 7 visual scenes.

============================================================
EXTREMELY IMPORTANT HOOK RULE
============================================================

THE FIRST 0-3 SECONDS ARE THE MOST IMPORTANT PART.

Scene 1 MUST:
- start at 0 seconds
- end at 3 seconds
- contain the strongest curiosity hook
- use 8-14 Hindi words when possible
- be naturally speakable in about 3 seconds
- create an immediate curiosity gap
- preferably mention a specific Indian place/object/person
- NEVER waste time with greetings

The hook MUST be EXACTLY the same as:
"hook"
and:
scenes[0].narration

NEVER start with:
"आज हम बात करेंगे..."
"क्या आप जानते हैं..."
"नमस्कार दोस्तों..."
"दोस्तों आज की वीडियो में..."

============================================================
STORY STRUCTURE
============================================================

0-3 sec:
EXTREMELY STRONG HOOK.

3-7 sec:
Mystery setup.

7-17 sec:
Clue chain.

17-27 sec:
Strongest documented revelation.

Final seconds:
Unanswered question / comment bait.

Final scene MUST ask a question that encourages comments.

============================================================
FACTUAL RULE
============================================================

Only established information may be presented as fact.

For uncertain claims use wording such as:
"एक सिद्धांत के अनुसार..."
"कुछ इतिहासकार मानते हैं..."
"लोककथाओं के अनुसार..."
"आज तक इसका निश्चित जवाब नहीं मिला..."
"इस दावे की स्वतंत्र पुष्टि नहीं हुई है..."

Never invent:
- dates
- people
- discoveries
- scientific claims
- quotes
- archaeological evidence

Clearly separate folklore from documented history.

============================================================
VISUAL RULE
============================================================

Every pexels_query MUST target India or an Indian location.

Never request foreign visuals.

The visual query should match the exact narration
as closely as possible.

============================================================
SFX INTELLIGENCE
============================================================

DO NOT assign SFX using a fixed scene-number pattern.

Choose the SFX according to the actual story/reaction.

Available SFX:
- whoosh
- impact
- heartbeat
- hit

Use:

whoosh:
movement, transition, entering a place, reveal transition,
rapid clue movement.

impact:
major reveal, shocking historical fact, strongest discovery.

heartbeat:
fear, suspense, uncertainty, unexplained mystery,
dark atmosphere.

hit:
sudden event, danger, dramatic punch, unexpected moment.

Every scene should have a suitable SFX when possible.

Return:
"sfx": "whoosh"
"sfx_reason": "movement into the hidden tunnel"
"emotion": "curiosity"
"reaction": "sudden reveal"

============================================================
CAPTION RULE
============================================================

DO NOT CREATE CAPTIONS.

There is NO caption field.

============================================================
SEO RULE
============================================================

Generate SEO specifically for this exact video.

TITLE:
- Hindi
- curiosity-driven
- natural
- not misleading
- maximum 100 characters
- include #Shorts naturally when appropriate

DESCRIPTION:
- Hindi
- around 100-180 words
- summarize actual story
- include naturally relevant search keywords
- do NOT keyword-stuff
- include relevant hashtags

TAGS:
Generate 12-25 highly relevant YouTube search tags.

HASHTAGS:
Generate 6-12 relevant hashtags.

============================================================
RETURN ONLY VALID JSON
============================================================

{{
  "topic": "{topic}",
  "title": "... #Shorts",
  "description": "...",
  "hook": "...",
  "scenes": [
    {{
      "scene_number": 1,
      "start_time": 0,
      "end_time": 3,
      "narration": "...",
      "pexels_query": "...",
      "sfx": "heartbeat",
      "sfx_reason": "suspenseful opening",
      "emotion": "fear",
      "reaction": "curiosity",
      "scene_purpose": "hook"
    }}
  ],
  "seo": {{
    "title": "... #Shorts",
    "description": "...",
    "tags": [
      "...",
      "..."
    ],
    "hashtags": [
      "#...",
      "#..."
    ]
  }}
}}

IMPORTANT:
Exactly 7 scenes.
No caption fields.
Scene 1 is exactly 0-3 seconds.
Scene 1 narration MUST equal hook.
SFX must be selected according to the story, NOT scene number.
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a factual, high-retention Hindi "
                    "Indian dark-history YouTube Shorts writer "
                    "and SEO specialist."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.82,
        response_format={
            "type": "json_object"
        },
    )

    data = json.loads(
        response.choices[0].message.content
    )

    data = validate_indian_story(
        data,
        expected_topic=topic,
    )

    # --------------------------------------------------------
    # HARD 0-3 SECOND HOOK
    # --------------------------------------------------------

    hook = str(
        data.get(
            "hook",
            "",
        )
    ).strip()

    if not hook:

        hook = (
            "इस भारतीय रहस्य का जवाब आज तक क्यों नहीं मिला?"
        )

    hook_words = hook.split()

    if len(hook_words) > 18:

        hook = (
            " ".join(
                hook_words[:18]
            )
            .rstrip(
                " ,.!?"
            )
            + "?"
        )

    scenes = data["scenes"]

    if len(scenes) != 7:

        raise ValueError(
            "Story does not contain exactly 7 scenes."
        )

    for index, scene in enumerate(
        scenes,
        start=1,
    ):

        scene["scene_number"] = index

    scenes[0]["start_time"] = 0
    scenes[0]["end_time"] = 3
    scenes[0]["narration"] = hook

    # Make sure every scene has intelligent SFX.
    for scene in scenes:

        scene["sfx"] = choose_sfx_from_story(
            scene.get(
                "narration",
                "",
            ),
            scene.get(
                "sfx_reason",
                "",
            ),
            scene.get(
                "emotion",
                "",
            ),
            scene.get(
                "reaction",
                "",
            ),
            scene.get(
                "scene_purpose",
                "",
            ),
        )

    # Remove accidental caption fields.
    for scene in scenes:
        scene.pop(
            "caption",
            None,
        )

    data = normalize_seo(
        data,
        topic,
    )

    data["title"] = data[
        "seo"
    ][
        "title"
    ]

    data["description"] = data[
        "seo"
    ][
        "description"
    ]

    print(
        "\n🔥 0-3 SEC STRONG HOOK:"
    )

    print(
        hook
    )

    print(
        "\n🎬 SEO TITLE:"
    )

    print(
        data["seo"]["title"]
    )

    print(
        "\n📝 SEO DESCRIPTION:"
    )

    print(
        data["seo"]["description"]
    )

    print(
        "\n🏷️ SEO TAGS:"
    )

    print(
        ", ".join(
            data["seo"]["tags"]
        )
    )

    print(
        "\n#️⃣ HASHTAGS:"
    )

    print(
        " ".join(
            data["seo"]["hashtags"]
        )
    )

    print(
        "\n💥 STORY-BASED SFX PLAN:"
    )

    for scene in scenes:

        print(
            f"Scene {scene['scene_number']}: "
            f"{scene['sfx']} | "
            f"{scene.get('sfx_reason', '')}"
        )

    return data


# ============================================================
# PEXELS QUERY FALLBACK GENERATOR
# ============================================================

def generate_fallback_queries(
    original_query,
    narration,
    topic,
    scene_number,
):

    original_query = str(
        original_query or ""
    ).strip()

    narration = str(
        narration or ""
    ).strip()

    topic = str(
        topic or ""
    ).strip()

    queries = []

    # Original query first.
    if original_query:
        queries.append(
            original_query
        )

    # Exact topic.
    queries.extend(
        [
            topic,
            f"{topic} India",
            f"{topic} historical monument India",
        ]
    )

    # Narration.
    if narration:
        queries.extend(
            [
                f"India {narration}",
                f"Indian history {narration}",
            ]
        )

    # Generic scene-specific India fallbacks.
    fallback_sets = [
        [
            "India ancient fort",
            "Indian fort aerial",
            "Indian historical fort",
            "Rajasthan fort India",
        ],
        [
            "India ancient temple",
            "Indian temple architecture",
            "Indian historical temple",
            "India temple aerial",
        ],
        [
            "India ancient ruins",
            "Indian archaeological site",
            "India historical ruins",
            "Indian ancient architecture",
        ],
        [
            "India cave temple",
            "Indian caves history",
            "India archaeological caves",
            "Indian stone architecture",
        ],
        [
            "India old city",
            "Indian heritage city",
            "Indian historical place",
            "India heritage architecture",
        ],
        [
            "India historical monument",
            "Indian heritage monument",
            "India ancient architecture",
            "Indian history location",
        ],
        [
            "India mysterious place",
            "Indian historical place",
            "India ancient monument",
            "Indian heritage site",
        ],
    ]

    index = max(
        0,
        min(
            scene_number - 1,
            len(fallback_sets) - 1,
        ),
    )

    queries.extend(
        fallback_sets[index]
    )

    # Remove duplicates while preserving order.
    clean = []

    seen = set()

    for query in queries:

        try:

            query = ensure_india_query(
                query
            )

        except Exception:

            continue

        key = query.lower().strip()

        if key not in seen:

            seen.add(key)

            clean.append(
                query
            )

    # Shuffle fallback portion a little,
    # but keep original query first.
    if len(clean) > 1:

        first = clean[0]

        rest = clean[1:]

        random.shuffle(
            rest
        )

        clean = [
            first
        ] + rest

    return clean[
        :MAX_PEXELS_QUERY_ATTEMPTS
    ]


# ============================================================
# PEXELS SEARCH
# ============================================================

def search_pexels_video(
    query,
):

    query = ensure_india_query(
        query
    )

    print(
        f"\n🔎 PEXELS SEARCH: {query}"
    )

    url = (
        "https://api.pexels.com/videos/search"
    )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Mozilla/5.0",
    }

    orientations = [
        "portrait",
        "landscape",
    ]

    for orientation in orientations:

        params = {
            "query": query,
            "per_page": 20,
            "orientation": orientation,
            "size": "large",
        }

        for attempt in range(
            1,
            4,
        ):

            try:

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=(
                        20,
                        45,
                    ),
                )

                if response.status_code != 200:

                    print(
                        f"❌ Pexels error "
                        f"{response.status_code}"
                    )

                    if response.status_code in {
                        429,
                        500,
                        502,
                        503,
                        504,
                    }:

                        time.sleep(
                            2 * attempt
                        )

                        continue

                    break

                data = response.json()

                videos = data.get(
                    "videos",
                    [],
                )

                if not videos:
                    break

                candidates = []

                for video in videos:

                    for file in video.get(
                        "video_files",
                        [],
                    ):

                        width = (
                            file.get(
                                "width"
                            )
                            or 0
                        )

                        height = (
                            file.get(
                                "height"
                            )
                            or 0
                        )

                        link = file.get(
                            "link"
                        )

                        if not link:
                            continue

                        if (
                            width >= 720
                            or height >= 720
                        ):

                            candidates.append(
                                {
                                    "url": link,
                                    "width": width,
                                    "height": height,
                                    "duration": video.get(
                                        "duration",
                                        0,
                                    ),
                                }
                            )

                if not candidates:
                    break

                vertical = [
                    x
                    for x in candidates
                    if x["height"] > x["width"]
                ]

                if vertical:
                    candidates = vertical

                candidates.sort(
                    key=lambda x: (
                        x["width"]
                        * x["height"]
                    ),
                    reverse=True,
                )

                selected_pool = candidates[
                    :min(
                        10,
                        len(candidates),
                    )
                ]

                selected = random.choice(
                    selected_pool
                )

                print(
                    "✅ Selected:",
                    selected["width"],
                    "x",
                    selected["height"],
                    "| Duration:",
                    selected["duration"],
                )

                return selected

            except Exception as e:

                print(
                    f"⚠️ Pexels attempt "
                    f"{attempt}/3 failed:",
                    e,
                )

                if attempt < 3:

                    time.sleep(
                        3 * attempt
                    )

    return None


# ============================================================
# GET RELATED FOOTAGE WITH FALLBACKS
# ============================================================

def get_related_scene_video(
    scene_number,
    query,
    narration,
    topic,
):

    queries = generate_fallback_queries(
        original_query=query,
        narration=narration,
        topic=topic,
        scene_number=scene_number,
    )

    print(
        "\n"
        + "-" * 70
    )

    print(
        f"🎥 SCENE {scene_number} "
        f"FOOTAGE SEARCH"
    )

    print(
        f"🎯 Original query: {query}"
    )

    print(
        f"🔁 Fallback queries available: "
        f"{len(queries)}"
    )

    print(
        "-" * 70
    )

    for attempt, fallback_query in enumerate(
        queries,
        start=1,
    ):

        print(
            f"\n🔎 Scene {scene_number} "
            f"visual attempt "
            f"{attempt}/{len(queries)}"
        )

        print(
            f"Query: {fallback_query}"
        )

        result = search_pexels_video(
            fallback_query
        )

        if not result:

            print(
                "⚠️ No footage found."
            )

            continue

        filename = (
            f"scene_{scene_number}.mp4"
        )

        downloaded = download_video(
            result["url"],
            filename,
        )

        if downloaded:

            print(
                f"✅ Scene {scene_number} "
                f"footage ready."
            )

            return downloaded

        print(
            "⚠️ Download failed. "
            "Trying another related query..."
        )

    print(
        f"\n❌ Scene {scene_number}: "
        "ALL RELATED FOOTAGE ATTEMPTS FAILED."
    )

    return None


# ============================================================
# DOWNLOAD VIDEO
# ============================================================

def download_video(
    url,
    filename,
):

    path = CLIPS_DIR / filename

    # Remove old file first.
    try:

        if path.exists():
            path.unlink()

    except Exception:
        pass

    print(
        f"⬇️ Downloading {filename}"
    )

    for attempt in range(
        1,
        4,
    ):

        try:

            print(
                f"   Download attempt "
                f"{attempt}/3"
            )

            with requests.get(
                url,
                stream=True,
                timeout=(
                    20,
                    180,
                ),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "Chrome/151 Safari/537.36"
                    )
                },
            ) as response:

                response.raise_for_status()

                with open(
                    path,
                    "wb",
                ) as file:

                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):

                        if chunk:
                            file.write(
                                chunk
                            )

            if (
                path.exists()
                and path.stat().st_size > 10000
            ):

                print(
                    "✅ Saved:",
                    path,
                )

                return str(path)

        except Exception as e:

            print(
                f"⚠️ Download attempt "
                f"{attempt} failed:",
                e,
            )

            if attempt < 3:

                time.sleep(
                    3 * attempt
                )

    print(
        f"❌ Could not download "
        f"{filename}"
    )

    return None


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
        AUDIO_DIR
        / f"voice_{scene_number}.mp3"
    )

    print(
        f"🎙️ Generating Hindi voice "
        f"scene {scene_number}"
    )

    asyncio.run(
        create_voice(
            text,
            str(filename),
        )
    )

    if (
        not filename.exists()
        or filename.stat().st_size < 1000
    ):

        raise RuntimeError(
            f"Voice generation failed "
            f"for scene {scene_number}."
        )

    return str(filename)


# ============================================================
# VIDEO FORMAT
# ============================================================

def prepare_clip_for_shorts(
    clip
):

    width = clip.w
    height = clip.h

    target_ratio = (
        VIDEO_WIDTH
        / VIDEO_HEIGHT
    )

    current_ratio = (
        width
        / height
    )

    if current_ratio > target_ratio:

        new_width = int(
            height
            * target_ratio
        )

        x1 = (
            width
            - new_width
        ) // 2

        clip = clip.cropped(
            x1=x1,
            x2=x1 + new_width,
        )

    else:

        new_height = int(
            width
            / target_ratio
        )

        y1 = (
            height
            - new_height
        ) // 2

        clip = clip.cropped(
            y1=y1,
            y2=y1 + new_height,
        )

    return clip.resized(
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
    )


def create_rapid_segments(
    video,
    target_duration,
):

    if video.duration <= 0:
        return []

    segments = []

    segment_count = max(
        2,
        math.ceil(
            target_duration
            / 2.5
        ),
    )

    segment_duration = (
        target_duration
        / segment_count
    )

    for i in range(
        segment_count
    ):

        if (
            video.duration
            <= segment_duration
        ):

            start = 0

        else:

            available = (
                video.duration
                - segment_duration
            )

            start = (
                available
                * i
                / max(
                    1,
                    segment_count - 1,
                )
            )

        end = min(
            start + segment_duration,
            video.duration,
        )

        if end <= start:
            continue

        piece = video.subclipped(
            start,
            end,
        )

        piece = prepare_clip_for_shorts(
            piece
        )

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

        segments.append(
            piece
        )

    return segments


# ============================================================
# AUDIO / SFX
# ============================================================

def load_sfx(
    effect_name
):

    mapping = {
        "whoosh": WHOOSH_FILE,
        "impact": IMPACT_FILE,
        "heartbeat": HEARTBEAT_FILE,
        "hit": HIT_FILE,
    }

    file_path = mapping.get(
        str(
            effect_name or ""
        ).lower().strip()
    )

    if (
        not file_path
        or not file_path.exists()
    ):

        return None

    return str(file_path)


def get_available_sfx():

    available = []

    for name in (
        "whoosh",
        "impact",
        "heartbeat",
        "hit",
    ):

        if load_sfx(name):
            available.append(name)

    return available


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

    return concatenate_audioclips(
        pieces
    )


def create_sfx_layer(
    sfx_name,
    duration,
    narration,
    reason,
    emotion,
    reaction,
):

    available = get_available_sfx()

    if not available:

        print(
            "⚠️ No SFX files found in sfx folder."
        )

        return None

    requested = str(
        sfx_name or ""
    ).lower().strip()

    # If AI-selected SFX does not exist,
    # intelligently choose another available one.
    if requested not in available:

        requested = choose_sfx_from_story(
            narration,
            reason,
            emotion,
            reaction,
            "",
        )

    if requested not in available:

        requested = random.choice(
            available
        )

    sfx_file = load_sfx(
        requested
    )

    if not sfx_file:
        return None

    try:

        sfx = AudioFileClip(
            sfx_file
        )

        if sfx.duration <= 0:

            sfx.close()

            return None

        sfx_duration = min(
            sfx.duration,
            MAX_SFX_DURATION,
            duration,
        )

        sfx = sfx.subclipped(
            0,
            sfx_duration,
        )

        intensity = get_sfx_intensity(
            requested,
            narration,
            reason,
            emotion,
            reaction,
        )

        volume = (
            SFX_BASE_VOLUME
            * intensity
        )

        # Keep within reasonable range.
        volume = max(
            0.40,
            min(
                1.0,
                volume,
            ),
        )

        sfx = sfx.with_volume_scaled(
            volume
        )

        # Start SFX almost immediately.
        # This makes hook/reveal effects audible.
        sfx = sfx.with_start(
            0.02
        )

        print(
            f"💥 SFX: {requested} | "
            f"volume={volume:.2f} | "
            f"reason={reason or 'story reaction'}"
        )

        return sfx

    except Exception as e:

        print(
            f"⚠️ SFX creation failed "
            f"({requested}):",
            e,
        )

        return None


# ============================================================
# BUILD SCENE
# ============================================================

def build_scene(
    video_path,
    audio_path,
    scene_number,
    sfx_name=None,
    sfx_reason="",
    emotion="",
    reaction="",
    narration="",
):

    print(
        f"\n🎬 Building scene "
        f"{scene_number}"
    )

    narration_audio = None
    source_video = None

    try:

        narration_audio = AudioFileClip(
            audio_path
        )

        duration = narration_audio.duration

        if duration <= 0:

            raise RuntimeError(
                f"Scene {scene_number} "
                "voice duration is invalid."
            )

        source_video = VideoFileClip(
            video_path
        )

        if source_video.duration <= 0:

            raise RuntimeError(
                f"Scene {scene_number} "
                "source video duration is invalid."
            )

        if source_video.duration < duration:

            loops = (
                int(
                    duration
                    / max(
                        source_video.duration,
                        0.1,
                    )
                )
                + 1
            )

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

        rapid_segments = (
            create_rapid_segments(
                video,
                duration,
            )
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

        # ----------------------------------------------------
        # SFX
        # ----------------------------------------------------

        audio_layers = [
            narration_audio
        ]

        sfx = create_sfx_layer(
            sfx_name=sfx_name,
            duration=duration,
            narration=narration,
            reason=sfx_reason,
            emotion=emotion,
            reaction=reaction,
        )

        if sfx:

            audio_layers.append(
                sfx
            )

        else:

            print(
                f"⚠️ Scene {scene_number}: "
                "SFX unavailable."
            )

        combined_audio = (
            CompositeAudioClip(
                audio_layers
            )
        )

        final_scene = CompositeVideoClip(
            [video],
            size=(
                VIDEO_WIDTH,
                VIDEO_HEIGHT,
            ),
        )

        final_scene = final_scene.with_audio(
            combined_audio
        )

        return final_scene

    except Exception:

        try:

            if narration_audio:
                narration_audio.close()

        except Exception:
            pass

        try:

            if source_video:
                source_video.close()

        except Exception:
            pass

        raise


# ============================================================
# BGM
# ============================================================

def add_background_music(
    final_video
):

    if not BGM_FILE.exists():

        print(
            "⚠️ bgm.mp3 not found."
        )

        return final_video

    print(
        "🎵 Adding suspense BGM..."
    )

    bgm = None

    try:

        bgm = AudioFileClip(
            str(BGM_FILE)
        )

        bgm = make_looped_audio(
            bgm,
            final_video.duration,
        )

        bgm = bgm.with_volume_scaled(
            BGM_VOLUME
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

    except Exception as e:

        print(
            "⚠️ BGM failed:",
            e,
        )

        try:

            if bgm:
                bgm.close()

        except Exception:
            pass

        return final_video


# ============================================================
# THUMBNAIL
# ============================================================

def find_font():

    fonts = [
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    for font in fonts:

        if os.path.exists(font):
            return font

    return None


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

    try:

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

        image = (
            Image.fromarray(frame)
            .convert("RGB")
            .resize(
                (
                    1280,
                    720,
                )
            )
            .filter(
                ImageFilter.SHARPEN
            )
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

        words = str(
            title
        ).split()

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
            bbox[2]
            - bbox[0]
        )

        x = (
            1280
            - text_width
        ) // 2

        y = 530

        padding = 22

        draw.rounded_rectangle(
            (
                x - padding,
                y - padding,
                x + text_width + padding,
                y + 100,
            ),
            radius=20,
            fill=(0, 0, 0, 190),
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
            THUMBNAIL_DIR
            / "mystery_thumbnail.jpg"
        )

        image.save(
            output,
            quality=95,
        )

        print(
            "✅ Thumbnail:",
            output,
        )

        return str(output)

    finally:

        video.close()


# ============================================================
# VIDEO VALIDATION
# ============================================================

def validate_completed_video(
    video_path,
    expected_scene_count=7,
):

    print(
        "\n🔍 VALIDATING COMPLETED VIDEO..."
    )

    path = Path(
        video_path
    )

    if not path.exists():

        raise RuntimeError(
            "Final video file does not exist."
        )

    if path.stat().st_size < 100_000:

        raise RuntimeError(
            "Final video file is suspiciously small."
        )

    video = None

    try:

        video = VideoFileClip(
            str(path)
        )

        duration = float(
            video.duration or 0
        )

        if duration <= 0:

            raise RuntimeError(
                "Final video duration is invalid."
            )

        if video.w != VIDEO_WIDTH:
            raise RuntimeError(
                f"Invalid video width: {video.w}"
            )

        if video.h != VIDEO_HEIGHT:
            raise RuntimeError(
                f"Invalid video height: {video.h}"
            )

        if duration < 5:

            raise RuntimeError(
                "Final video is too short."
            )

        if duration > (
            MAX_SHORT_DURATION + 0.5
        ):

            raise RuntimeError(
                "Final video exceeds maximum duration."
            )

        print(
            f"✅ Video validation passed: "
            f"{video.w}x{video.h}, "
            f"{duration:.2f}s"
        )

        return True

    finally:

        if video:

            try:
                video.close()

            except Exception:
                pass


# ============================================================
# ASSEMBLE FULL SHORT
# ============================================================

def assemble_video(
    story
):

    print(
        "\n"
        + "=" * 75
    )

    print(
        "🎞️ BUILDING HIGH-RETENTION SHORT"
    )

    print(
        "=" * 75
    )

    scenes = story.get(
        "scenes",
        [],
    )

    # --------------------------------------------------------
    # HARD REQUIREMENT: exactly 7 scenes.
    # --------------------------------------------------------

    if len(scenes) != 7:

        raise RuntimeError(
            f"❌ Cannot build video. "
            f"Expected 7 scenes, got {len(scenes)}."
        )

    scene_clips = []

    created_scene_numbers = set()

    try:

        for scene in scenes:

            number = int(
                scene.get(
                    "scene_number"
                )
            )

            if number in created_scene_numbers:

                raise RuntimeError(
                    f"Duplicate scene number: {number}"
                )

            query = scene.get(
                "pexels_query",
                "",
            )

            narration = scene.get(
                "narration",
                "",
            )

            sfx = scene.get(
                "sfx"
            )

            sfx_reason = scene.get(
                "sfx_reason",
                "",
            )

            emotion = scene.get(
                "emotion",
                "",
            )

            reaction = scene.get(
                "reaction",
                "",
            )

            print(
                f"\n🎥 SCENE {number}"
            )

            if number == 1:

                print(
                    "🔥 0-3 SEC "
                    "EXTREMELY STRONG HOOK"
                )

            print(
                "Visual:",
                query,
            )

            print(
                "Narration:",
                narration,
            )

            print(
                "SFX:",
                sfx,
            )

            print(
                "SFX reason:",
                sfx_reason,
            )

            # ------------------------------------------------
            # NEVER SKIP A SCENE.
            #
            # If original footage unavailable, try fallback
            # queries. If all fail, abort complete video.
            # ------------------------------------------------

            video_file = (
                get_related_scene_video(
                    scene_number=number,
                    query=query,
                    narration=narration,
                    topic=story.get(
                        "topic",
                        "",
                    ),
                )
            )

            if not video_file:

                raise RuntimeError(
                    f"❌ Scene {number} "
                    "could not obtain any related "
                    "Indian footage."
                )

            audio_file = generate_voice(
                narration,
                number,
            )

            clip = build_scene(
                video_file,
                audio_file,
                number,
                sfx,
                sfx_reason,
                emotion,
                reaction,
                narration,
            )

            if clip is None:

                raise RuntimeError(
                    f"Scene {number} "
                    "clip creation failed."
                )

            scene_clips.append(
                clip
            )

            created_scene_numbers.add(
                number
            )

            print(
                f"✅ Scene {number}/7 completed."
            )

        # ----------------------------------------------------
        # HARD REQUIREMENT: all seven scenes.
        # ----------------------------------------------------

        if len(scene_clips) != 7:

            raise RuntimeError(
                "❌ Video assembly aborted: "
                f"only {len(scene_clips)}/7 scenes completed."
            )

        if created_scene_numbers != {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
        }:

            raise RuntimeError(
                "❌ Scene validation failed. "
                "All scene numbers 1-7 are required."
            )

        print(
            "\n🔗 Joining all 7 scenes..."
        )

        final_video = (
            concatenate_videoclips(
                scene_clips,
                method="compose",
            )
        )

        final_video = (
            add_background_music(
                final_video
            )
        )

        if (
            final_video.duration
            > MAX_SHORT_DURATION
        ):

            print(
                f"\n✂️ Final video is "
                f"{final_video.duration:.2f}s. "
                f"Trimming to "
                f"{MAX_SHORT_DURATION:.0f}s..."
            )

            final_video = (
                final_video.subclipped(
                    0,
                    MAX_SHORT_DURATION,
                )
            )

        output = (
            OUTPUT_DIR
            / "mystery_short.mp4"
        )

        # Remove old output before export.
        try:

            if output.exists():
                output.unlink()

        except Exception:
            pass

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
            logger="bar",
        )

        duration = (
            final_video.duration
        )

        final_video.close()

        # ----------------------------------------------------
        # VERY IMPORTANT:
        # Validate MP4 BEFORE allowing upload.
        # ----------------------------------------------------

        validate_completed_video(
            output,
            expected_scene_count=7,
        )

        print(
            "\n🎉 COMPLETE 7-SCENE VIDEO CREATED"
        )

        print(
            "⏱️ Duration:",
            round(
                duration,
                2,
            ),
            "seconds",
        )

        print(
            "📁",
            output,
        )

        return str(output)

    except Exception:

        # Close all already-created clips.
        for clip in scene_clips:

            try:
                clip.close()

            except Exception:
                pass

        # If failed, remove incomplete output.
        output = (
            OUTPUT_DIR
            / "mystery_short.mp4"
        )

        try:

            if output.exists():
                output.unlink()

        except Exception:
            pass

        raise

    finally:

        for clip in scene_clips:

            try:
                clip.close()

            except Exception:
                pass


# ============================================================
# YOUTUBE AUTHENTICATION
# ============================================================

def get_youtube_service():

    scopes = [
        YOUTUBE_SCOPE
    ]

    credentials = None

    # --------------------------------------------------------
    # 1. Existing token.json
    # --------------------------------------------------------

    if os.path.exists(
        TOKEN_FILE
    ):

        print(
            "🔐 Loading YouTube token.json..."
        )

        try:

            credentials = (
                Credentials.from_authorized_user_file(
                    TOKEN_FILE,
                    scopes,
                )
            )

        except Exception as e:

            print(
                "⚠️ token.json could not "
                "be loaded:",
                e,
            )

            credentials = None

    # --------------------------------------------------------
    # 2. Refresh
    # --------------------------------------------------------

    if (
        credentials is not None
        and credentials.expired
    ):

        if credentials.refresh_token:

            print(
                "🔄 Refreshing YouTube "
                "access token..."
            )

            try:

                credentials.refresh(
                    Request()
                )

                with open(
                    TOKEN_FILE,
                    "w",
                    encoding="utf-8",
                ) as token:

                    token.write(
                        credentials.to_json()
                    )

                print(
                    "✅ YouTube token refreshed."
                )

            except Exception as e:

                print(
                    "⚠️ Token refresh failed:",
                    e,
                )

                credentials = None

    # --------------------------------------------------------
    # 3. Valid token
    # --------------------------------------------------------

    if (
        credentials is not None
        and credentials.valid
    ):

        print(
            "✅ YouTube OAuth token is valid."
        )

        return build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    # --------------------------------------------------------
    # 4. client_secret.json
    # --------------------------------------------------------

    if not CLIENT_SECRET_FILE.exists():

        raise RuntimeError(
            "\n"
            "❌ client_secret.json missing.\n\n"
            "For GitHub Actions, create a GitHub Secret:\n"
            "CLIENT_SECRET_JSON\n\n"
            "It must contain the COMPLETE Google OAuth "
            "client_secret.json contents.\n"
        )

    # --------------------------------------------------------
    # 5. Local first OAuth
    # --------------------------------------------------------

    print(
        "🔑 Starting YouTube OAuth..."
    )

    flow = (
        InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes,
        )
    )

    if (
        os.getenv(
            "GITHUB_ACTIONS",
            "",
        ).lower()
        == "true"
    ):

        raise RuntimeError(
            "\n"
            "❌ YouTube token.json is missing "
            "or expired in GitHub Actions.\n\n"
            "Run the script locally once, "
            "complete Google OAuth, then save "
            "token.json as YOUTUBE_TOKEN_JSON.\n"
        )

    credentials = flow.run_local_server(
        port=0,
        open_browser=True,
    )

    with open(
        TOKEN_FILE,
        "w",
        encoding="utf-8",
    ) as token:

        token.write(
            credentials.to_json()
        )

    print(
        "✅ YouTube token.json created."
    )

    return build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


# ============================================================
# YOUTUBE UPLOAD RETRIES
# ============================================================

def _is_retryable_youtube_error(
    error
):

    text = str(
        error
    ).lower()

    retry_terms = [
        "10053",
        "10054",
        "10060",
        "connection aborted",
        "connection reset",
        "connection broken",
        "remote end closed",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "internal error",
        "backend error",
        "rate limit",
        "too many requests",
        "503",
        "502",
        "500",
        "504",
    ]

    if any(
        term in text
        for term in retry_terms
    ):
        return True

    if isinstance(
        error,
        HttpError
    ):

        try:

            status = int(
                error.resp.status
            )

            return status in {
                408,
                429,
                500,
                502,
                503,
                504,
            }

        except Exception:

            return False

    return False


def _upload_video_resumable(
    youtube,
    video_path,
    body,
):

    media = MediaFileUpload(
        str(video_path),
        chunksize=(
            YOUTUBE_UPLOAD_CHUNK_SIZE
        ),
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(
        "📦 Upload mode: resumable "
        "chunks of "
        f"{YOUTUBE_UPLOAD_CHUNK_SIZE // (1024 * 1024)} MB"
    )

    response = None
    last_error = None

    while response is None:

        try:

            status, response = (
                request.next_chunk()
            )

            if status is not None:

                try:

                    progress = int(
                        status.progress()
                        * 100
                    )

                    print(
                        "📤 YouTube upload "
                        f"progress: {progress}%",
                        flush=True,
                    )

                except Exception:
                    pass

            if response is not None:
                break

        except Exception as error:

            last_error = error

            if not _is_retryable_youtube_error(
                error
            ):
                raise

            print(
                "⚠️ Temporary YouTube "
                "upload/network error:"
            )

            print(
                error
            )

            recovered = False

            for retry in range(
                1,
                YOUTUBE_UPLOAD_MAX_RETRIES + 1,
            ):

                delay = min(
                    60,
                    2 ** retry,
                )

                print(
                    f"🔄 Upload retry "
                    f"{retry}/"
                    f"{YOUTUBE_UPLOAD_MAX_RETRIES} "
                    f"in {delay}s..."
                )

                time.sleep(
                    delay
                )

                try:

                    status, response = (
                        request.next_chunk()
                    )

                    if status is not None:

                        try:

                            progress = int(
                                status.progress()
                                * 100
                            )

                            print(
                                "📤 YouTube upload "
                                f"progress: {progress}%",
                                flush=True,
                            )

                        except Exception:
                            pass

                    recovered = True
                    break

                except Exception as retry_error:

                    last_error = (
                        retry_error
                    )

                    print(
                        f"⚠️ Retry {retry} failed:",
                        retry_error,
                    )

                    if not _is_retryable_youtube_error(
                        retry_error
                    ):
                        raise

            if not recovered:

                raise RuntimeError(
                    "YouTube resumable upload "
                    "failed after "
                    f"{YOUTUBE_UPLOAD_MAX_RETRIES} "
                    f"retries. Last error: "
                    f"{last_error}"
                ) from last_error

    if (
        not response
        or not response.get("id")
    ):

        raise RuntimeError(
            "YouTube upload finished "
            "without a video ID."
        )

    return response["id"]


def _upload_thumbnail_with_retry(
    youtube,
    video_id,
    thumbnail_path,
):

    if (
        not thumbnail_path
        or not os.path.exists(
            thumbnail_path
        )
    ):

        return

    print(
        "🖼️ Uploading custom thumbnail..."
    )

    last_error = None

    for attempt in range(
        1,
        4,
    ):

        try:

            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(thumbnail_path),
                    mimetype="image/jpeg",
                ),
            ).execute()

            print(
                "✅ Thumbnail uploaded."
            )

            return

        except Exception as error:

            last_error = error

            print(
                f"⚠️ Thumbnail attempt "
                f"{attempt}/3 failed:",
                error,
            )

            if (
                attempt < 3
                and _is_retryable_youtube_error(
                    error
                )
            ):

                time.sleep(
                    2 * attempt
                )

            else:

                break

    print(
        "⚠️ Thumbnail upload failed "
        "after retries:",
        last_error,
    )


# ============================================================
# YOUTUBE UPLOAD WITH SEO
# ============================================================

def upload_to_youtube(
    video_path,
    title,
    description,
    thumbnail_path=None,
    seo=None,
):

    # --------------------------------------------------------
    # ABSOLUTE SAFETY:
    # Validate video one more time immediately before upload.
    # --------------------------------------------------------

    validate_completed_video(
        video_path,
        expected_scene_count=7,
    )

    print(
        "\n📤 UPLOADING TO YOUTUBE..."
    )

    youtube = get_youtube_service()

    seo = (
        seo
        if isinstance(
            seo,
            dict,
        )
        else {}
    )

    final_title = str(
        seo.get(
            "title",
            title
            or "Indian Mystery Short #Shorts",
        )
    ).strip()

    final_description = str(
        seo.get(
            "description",
            description
            or "",
        )
    ).strip()

    tags = seo.get(
        "tags",
        [],
    )

    if not isinstance(
        tags,
        list,
    ):
        tags = []

    tags = [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]

    core_tags = [
        "Shorts",
        "Indian Mystery",
        "Indian History",
        "India Facts",
        "Hindi Facts",
        "Hindi Mystery",
    ]

    for tag in core_tags:

        if tag.lower() not in {
            x.lower()
            for x in tags
        }:

            tags.append(
                tag
            )

    tags = tags[:30]

    final_title = final_title[:100]

    body = {
        "snippet": {
            "title": final_title,
            "description": final_description,
            "tags": tags,
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    print(
        "\n📌 UPLOAD SEO"
    )

    print(
        "TITLE:",
        final_title,
    )

    print(
        "TAGS:",
        ", ".join(tags),
    )

    print(
        "DESCRIPTION:"
    )

    print(
        final_description
    )

    file_size_mb = (
        os.path.getsize(
            video_path
        )
        / (
            1024 * 1024
        )
        if os.path.exists(
            video_path
        )
        else 0
    )

    print(
        f"🎬 Video size: "
        f"{file_size_mb:.2f} MB"
    )

    video_id = (
        _upload_video_resumable(
            youtube,
            video_path,
            body,
        )
    )

    print(
        "\n🎉 YOUTUBE UPLOAD SUCCESS"
    )

    print(
        "🆔 Video ID:",
        video_id,
    )

    print(
        "🔗 https://www.youtube.com/watch?v="
        + video_id
    )

    _upload_thumbnail_with_retry(
        youtube,
        video_id,
        thumbnail_path,
    )

    return video_id


# ============================================================
# CLEANUP
# ============================================================

def cleanup_old_scene_files():

    print(
        "\n🧹 Cleaning old temporary files..."
    )

    for folder in (
        CLIPS_DIR,
        AUDIO_DIR,
    ):

        if not folder.exists():
            continue

        for item in folder.iterdir():

            try:

                if item.is_file():
                    item.unlink()

            except Exception:
                pass

    # Remove previous incomplete final video.
    old_video = (
        OUTPUT_DIR
        / "mystery_short.mp4"
    )

    try:

        if old_video.exists():
            old_video.unlink()

    except Exception:
        pass


# ============================================================
# RETRY ENTIRE VIDEO GENERATION
# ============================================================

def generate_complete_video_with_retry():

    last_error = None

    for attempt in range(
        1,
        MAX_FULL_VIDEO_ATTEMPTS + 1,
    ):

        print(
            "\n"
            + "=" * 75
        )

        print(
            f"🔄 COMPLETE VIDEO GENERATION "
            f"ATTEMPT {attempt}/"
            f"{MAX_FULL_VIDEO_ATTEMPTS}"
        )

        print(
            "=" * 75
        )

        # ----------------------------------------------------
        # Each full attempt gets a completely fresh topic.
        # ----------------------------------------------------

        try:

            cleanup_old_scene_files()

            story = generate_mystery_story()

            print(
                "\n📜 GENERATED STORY:"
            )

            print(
                json.dumps(
                    story,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            video_path = assemble_video(
                story
            )

            # ------------------------------------------------
            # Final validation.
            # ------------------------------------------------

            validate_completed_video(
                video_path,
                expected_scene_count=7,
            )

            print(
                "\n"
                + "=" * 75
            )

            print(
                "🎉 COMPLETE VIDEO GENERATION SUCCESS"
            )

            print(
                "=" * 75
            )

            return (
                story,
                video_path,
            )

        except Exception as e:

            last_error = e

            print(
                "\n"
                + "=" * 75
            )

            print(
                f"⚠️ COMPLETE VIDEO ATTEMPT "
                f"{attempt} FAILED"
            )

            print(
                "=" * 75
            )

            print(
                "Reason:",
                e,
            )

            # ------------------------------------------------
            # IMPORTANT:
            # Do NOT mark topic as used here.
            #
            # Because video did not successfully complete.
            # ------------------------------------------------

            cleanup_old_scene_files()

            if attempt < MAX_FULL_VIDEO_ATTEMPTS:

                delay = min(
                    30,
                    5 * attempt,
                )

                print(
                    f"\n🔁 Starting complete "
                    f"video generation again "
                    f"in {delay} seconds..."
                )

                time.sleep(
                    delay
                )

    raise RuntimeError(
        "\n❌ COMPLETE VIDEO GENERATION FAILED.\n"
        f"All {MAX_FULL_VIDEO_ATTEMPTS} attempts failed.\n"
        f"Last error: {last_error}"
    ) from last_error


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n"
    )

    print(
        "=" * 75
    )

    print(
        "🇮🇳 INDIA-ONLY DARK HISTORY & MYSTERY SHORTS AUTOBOT"
    )

    print(
        "=" * 75
    )

    print(
        "🎙️ Male Hindi Voice:",
        VOICE,
    )

    print(
        "⚡ Voice Speed:",
        VOICE_RATE,
    )

    print(
        "🔥 Hook:",
        "EXTREMELY STRONG / 0-3 SEC",
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
        "💥 Story-Based SFX:",
        "Enabled",
    )

    print(
        "🔊 SFX Volume:",
        f"{SFX_BASE_VOLUME:.2f}",
    )

    print(
        "🎵 BGM Volume:",
        f"{BGM_VOLUME:.2f}",
    )

    print(
        "📝 Captions:",
        "DISABLED / REMOVED",
    )

    print(
        "🖼️ Thumbnail:",
        "Enabled",
    )

    print(
        "🔍 SEO:",
        "Title + Description + Tags + Hashtags",
    )

    print(
        "♻️ Duplicate Topics:",
        "BLOCKED",
    )

    print(
        "📚 Topic History:",
        USED_TOPICS_FILE,
    )

    print(
        "▶️ YouTube Upload:",
        "ONLY AFTER COMPLETE VIDEO VALIDATION",
    )

    print(
        "🎥 Scene Completion:",
        "7/7 REQUIRED",
    )

    print(
        "🔁 Full Video Retry:",
        f"{MAX_FULL_VIDEO_ATTEMPTS} attempts",
    )

    print(
        "🔎 Pexels Fallbacks:",
        f"{MAX_PEXELS_QUERY_ATTEMPTS} queries/scene",
    )

    print(
        "🇮🇳 Niche:",
        "INDIA ONLY — Indian Facts / History / Mysteries",
    )

    print(
        "=" * 75
    )

    # --------------------------------------------------------
    # Show available SFX.
    # --------------------------------------------------------

    available_sfx = get_available_sfx()

    print(
        "\n🎧 AVAILABLE SFX:"
    )

    if available_sfx:

        for item in available_sfx:

            print(
                f"   ✅ {item}.mp3"
            )

    else:

        print(
            "   ❌ No SFX files found!"
        )

        print(
            "   Put these files inside:"
        )

        print(
            "   sfx/whoosh.mp3"
        )

        print(
            "   sfx/impact.mp3"
        )

        print(
            "   sfx/heartbeat.mp3"
        )

        print(
            "   sfx/hit.mp3"
        )

    # --------------------------------------------------------
    # Complete video generation.
    #
    # This function will NOT return until a complete 7/7
    # video has been successfully generated.
    # --------------------------------------------------------

    story, video_path = (
        generate_complete_video_with_retry()
    )

    # --------------------------------------------------------
    # Thumbnail ONLY AFTER complete video.
    # --------------------------------------------------------

    thumbnail = create_thumbnail(
        video_path,
        story.get(
            "title",
            "Mystery",
        ),
    )

    # --------------------------------------------------------
    # Verify video again before YouTube.
    # --------------------------------------------------------

    validate_completed_video(
        video_path,
        expected_scene_count=7,
    )

    # --------------------------------------------------------
    # YouTube upload.
    #
    # If upload fails, topic is STILL marked as used because
    # the complete video was successfully created.
    # --------------------------------------------------------

    upload_success = False

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
            story.get(
                "seo",
                {},
            ),
        )

        upload_success = True

    except Exception as e:

        print(
            "\n⚠️ YouTube upload "
            "skipped/failed:"
        )

        print(
            e
        )

    # --------------------------------------------------------
    # IMPORTANT TOPIC HISTORY RULE
    #
    # The topic is saved only because the complete video was
    # successfully generated and validated.
    #
    # If video generation failed, this code never reaches here.
    # --------------------------------------------------------

    if os.path.exists(
        video_path
    ):

        mark_topic_used(
            story["topic"]
        )

        print(
            "♻️ Duplicate topic protection: "
            "ACTIVE"
        )

    print(
        "\n"
        + "=" * 75
    )

    print(
        "🎉 COMPLETE"
    )

    print(
        "=" * 75
    )

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

    print(
        "📚 Used topics file:",
        os.path.abspath(
            USED_TOPICS_FILE
        ),
    )

    print(
        "📌 Current topic:",
        story["topic"],
    )

    print(
        "🎥 Scenes:",
        "7/7 COMPLETE",
    )

    print(
        "🔒 Topic saved:",
        "YES",
    )

    print(
        "▶️ YouTube upload:",
        "SUCCESS"
        if upload_success
        else "FAILED / SKIPPED",
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print(
            "\n"
            + "=" * 75
        )

        print(
            "❌ FATAL ERROR"
        )

        print(
            "=" * 75
        )

        print(
            e
        )

        raise
