import json
import re
import hashlib
import unicodedata
from pathlib import Path
from collections import defaultdict

root = Path(__file__).resolve().parents[1]

source = root / "data/podcasts.json"
target = root / "data/podcast_navigation.json"

data = json.loads(source.read_text(encoding="utf-8-sig"))
original = data.get("episodes", [])

if not original:
    raise RuntimeError("No podcast episodes found")

# Explicit Part markers only; never guess from unrelated numbers.
part_re = re.compile(
    r"(?i)(?:\b(?:part|pt|episode|ep)\s*[-:#.]?\s*(\d+)\b)"
    r"|(?:পর্ব|পার্ট|অংশ)\s*[-:#.]?\s*([0-9০-৯]+)"
)

def english_digits(s):
    return s.translate(str.maketrans(
        "০১২৩৪৫৬৭৮৯", "0123456789"
    ))

def make_id(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()[:16]

def clean_title(s):
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", " ", s)
    return s.strip()

episodes = []
groups = defaultdict(list)

for index, item in enumerate(original):
    title = clean_title(item.get("title", ""))
    url = item.get("audio_url", "")
    source_name = item.get("source", "unknown")

    if not title or not url.startswith("https://"):
        continue

    match = part_re.search(title)

    if match:
        part_text = next(
            x for x in match.groups() if x
        )
        part = int(english_digits(part_text))
        base = part_re.sub(" ", title)
        base = re.sub(r"\s+", " ", base)
        base = base.strip(" |-:,.")
    else:
        part = None
        base = title

    # A shared story ID requires an explicit Part marker.
    # No marker = independent standalone story.
    key = (
        str(source_name).casefold()
        + "|"
        + base.casefold()
    )

    if part is None:
        key += "|" + str(index)

    sid = make_id(key)

    eid = str(item.get("id") or make_id(
        title + "|" + url
    ))

    entry = {
        "id": eid,
        "story_id": sid,
        "story_title": base,
        "title": title,
        "category": item.get("category", "story"),
        "source": source_name,
        "part_number": part,
        "audio_url": url,
        "next_episode_id": None,
        "next_story_id": None
    }

    episodes.append(entry)
    groups[sid].append(entry)

if not episodes:
    raise RuntimeError("No valid episodes")

# Preserve first-appearance order for stories.
story_order = list(groups.keys())
warnings = []

for sid, items in groups.items():
    numbered = [
        x for x in items
        if x["part_number"] is not None
    ]

    by_number = defaultdict(list)
    for x in numbered:
        by_number[x["part_number"]].append(x)

    for x in numbered:
        if len(by_number[x["part_number"]]) > 1:
            warnings.append(
                "Duplicate part number: " + x["story_title"]
            )
            continue

        next_candidates = by_number.get(
            x["part_number"] + 1, []
        )

        if len(next_candidates) == 1:
            x["next_episode_id"] = next_candidates[0]["id"]

for idx, sid in enumerate(story_order):
    if idx + 1 >= len(story_order):
        continue

    next_sid = story_order[idx + 1]
    next_items = groups[next_sid]

    # Start the next story at Part 1 if available.
    first = next(
        (x for x in next_items if x["part_number"] == 1),
        next_items[0]
    )

    for entry in groups[sid]:
        entry["next_story_id"] = first["id"]

ids = [e["id"] for e in episodes]

if len(ids) != len(set(ids)):
    raise RuntimeError("Duplicate episode IDs")

output = {
    "schema_version": 2,
    "mode": "podcast",
    "total_episodes": len(episodes),
    "total_stories": len(groups),
    "navigation": {
        "next_episode": "same_story_next_part_only",
        "next_story": "next_distinct_story",
        "unknown_part": "do_not_guess"
    },
    "episodes": episodes
}

# Never overwrite the proven playback catalog.
target.write_text(
    json.dumps(output, ensure_ascii=False, indent=2)
    + "\n",
    encoding="utf-8"
)

print("====================================")
print("STEP 9: PODCAST NAVIGATION PASS")
print("Episodes:", len(episodes))
print("Stories:", len(groups))
print("Next Episode links:", sum(
    e["next_episode_id"] is not None
    for e in episodes
))
print("Next Story links:", sum(
    e["next_story_id"] is not None
    for e in episodes
))
print("Warnings:", len(warnings))

for warning in warnings[:10]:
    print("WARNING:", warning)

print("Output:", target)
print("Existing device catalog: UNCHANGED")
print("Firmware: UNCHANGED")
print("====================================")
