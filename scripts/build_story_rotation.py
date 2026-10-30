
import json
import re
import hashlib
import unicodedata
from pathlib import Path
from collections import Counter, deque

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "data/podcast_navigation.json"
OUTPUT = ROOT / "data/podcast_story_rotation.json"

SOURCES = (
    "sunday_suspense",
    "221b_harrison_road",
    "roll_sound_goppo",
)

KINDS = ("bengali", "foreign", "misc")
PATTERN = (
    "bengali", "foreign",
    "bengali", "foreign", "misc",
)

PART_RE = re.compile(
    r"\b(?:part|pt|episode|ep)\s*[-:#.]?\s*[0-9]+\b"
    r"|(?:পর্ব|পার্ট|অংশ)\s*[-:#.]?\s*[0-9০-৯]+",
    re.I,
)

FOREIGN_HINTS = (
    "arthur conan doyle",
    "agatha christie",
    "alexandre dumas",
    "bram stoker",
    "algernon blackwood",
    "edgar allan poe",
    "sherlock holmes",
    "roald dahl",
    "lovecraft",
    "maupassant",
    "শার্লক হোমস",
    "আগাথা ক্রিস্টি",
)

BENGALI_HINTS = (
    "satyajit ray",
    "shirshendu",
    "bibhutibhushan",
    "sunil gangopadhyay",
    "sukumar ray",
    "rabindranath",
    "narayan gangopadhyay",
    "bimal kar",
    "tarashankar",
    "syed mustafa siraj",
    "সত্যজিৎ",
    "বিভূতিভূষণ",
    "শীর্ষেন্দু",
    "রবীন্দ্রনাথ",
)


def genre(title):
    name = title.casefold()

    if any(x in name for x in FOREIGN_HINTS):
        return "foreign"

    if any(x in name for x in BENGALI_HINTS):
        return "bengali"

    return "misc"


def story_key(ep):
    source = ep["source"]

    # No explicit part means an independent story.
    if ep.get("part_number") is None:
        return source + "|single|" + ep["id"]

    title = ep["title"]

    # Normalize Sunday Suspense spelling variants.
    title = re.sub(
        r"sunday\s*s\s*uspense",
        "sundaysuspense",
        title,
        flags=re.I,
    )

    title = PART_RE.sub(" ", title)

    title = unicodedata.normalize(
        "NFKC", title
    ).casefold()

    title = "".join(
        c for c in title if c.isalnum()
    )

    return source + "|multipart|" + title


def main():
    navigation = json.loads(
        NAV.read_text(encoding="utf-8-sig")
    )
    original = navigation["episodes"]

    # Reuse previous classifications where available.
    previous = {}

    if OUTPUT.exists():
        old = json.loads(
            OUTPUT.read_text(encoding="utf-8-sig")
        )

        for ep in old.get("episodes", []):
            previous[ep["id"]] = ep.get(
                "writer_group", "misc"
            )

    stories = {}

    for position, ep in enumerate(original):
        assert ep["source"] in SOURCES
        assert ep["audio_url"].startswith("https://")

        key = story_key(ep)

        if key not in stories:
            stories[key] = {
                "key": key,
                "source": ep["source"],
                "episodes": [],
            }

        row = dict(ep)
        row["_position"] = position

        stories[key]["episodes"].append(row)

    # Sort every multipart story in ascending part order.
    for story in stories.values():
        story["episodes"].sort(
            key=lambda ep: (
                ep["part_number"]
                if ep["part_number"] is not None
                else 0,
                ep["_position"],
            )
        )

        votes = Counter()

        for ep in story["episodes"]:
            kind = previous.get(ep["id"])

            if kind not in KINDS:
                kind = genre(ep["title"])

            if kind != "misc":
                votes[kind] += 1

        story["kind"] = (
            votes.most_common(1)[0][0]
            if votes else "misc"
        )

    # Rotate complete stories, never individual parts.
    buckets = {
        source: {
            kind: deque()
            for kind in KINDS
        }
        for source in SOURCES
    }

    for story in stories.values():
        buckets[
            story["source"]
        ][
            story["kind"]
        ].append(story)

    ordered = []
    source_cursor = 0
    slot = 0

    while len(ordered) < len(stories):
        wanted = PATTERN[slot % len(PATTERN)]
        selected = None

        # Keep source order first.
        for offset in range(len(SOURCES)):
            index = (
                source_cursor + offset
            ) % len(SOURCES)

            source = SOURCES[index]

            priorities = (wanted,) + tuple(
                k for k in KINDS if k != wanted
            )

            for kind in priorities:
                if buckets[source][kind]:
                    selected = buckets[
                        source
                    ][kind].popleft()

                    source_cursor = (
                        index + 1
                    ) % len(SOURCES)
                    break

            if selected is not None:
                break

        if selected is None:
            raise RuntimeError(
                "Story queue exhausted unexpectedly"
            )

        ordered.append(selected)
        slot += 1

    episodes = []
    warnings = []

    for i, story in enumerate(ordered):
        parts = story["episodes"]

        next_story = (
            ordered[i + 1]["episodes"][0]["id"]
            if i + 1 < len(ordered)
            else ""
        )

        story_id = hashlib.sha256(
            story["key"].encode("utf-8")
        ).hexdigest()[:16]

        numbers = [
            ep["part_number"]
            for ep in parts
            if ep["part_number"] is not None
        ]

        for a, b in zip(numbers, numbers[1:]):
            if b != a + 1:
                warnings.append(
                    f"{story['key']}: part {a} to {b}"
                )

        for j, ep in enumerate(parts):
            row = {
                k: v for k, v in ep.items()
                if not k.startswith("_")
            }

            row["story_id"] = story_id
            row["writer_group"] = story["kind"]

            # The next part must belong to this story.
            row["next_episode_id"] = (
                parts[j + 1]["id"]
                if j + 1 < len(parts)
                else ""
            )

            # Different story only after current story.
            row["next_story_id"] = next_story

            episodes.append(row)

    ids = [ep["id"] for ep in episodes]

    assert len(ids) == len(original)
    assert len(ids) == len(set(ids))
    assert set(ids) == {
        ep["id"] for ep in original
    }

    for i, ep in enumerate(episodes):
        ep["next_queue_index"] = (
            i + 1
        ) % len(episodes)

    result = {
        "schema_version": 2,
        "mode": "podcast_story_rotation",
        "total": len(episodes),
        "total_stories": len(stories),
        "source_order": list(SOURCES),
        "unknown_writer": "misc",
        "navigation": {
            "next_episode": "same_story_only",
            "next_story": "next_distinct_story",
            "part_order": "ascending",
        },
        "episodes": episodes,
    }

    OUTPUT.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8",
    )

    print("STORY LEVEL ROTATION PASS")
    print("Episodes:", len(episodes))
    print("Stories:", len(stories))
    print("Missing episodes: 0")
    print("Part warnings:", len(warnings))

    for warning in warnings[:20]:
        print("WARNING:", warning)

    print("Existing device catalog: UNCHANGED")
    print("Firmware: UNCHANGED")


if __name__ == "__main__":
    main()
