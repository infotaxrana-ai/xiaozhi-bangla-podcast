
"""Build an optional Xiaozhi story rotation catalog.

Sources:
1. Sunday Suspense
2. 221B Harrison Road
3. Roll Sound

Unknown authors become misc.
All valid episodes remain in the queue.
Existing playback catalog stays unchanged.
"""

import json
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "podcasts.json"
OUTPUT = ROOT / "data" / "podcast_story_rotation.json"

SOURCE_ORDER = (
    "sunday_suspense",
    "221b_harrison_road",
    "roll_sound_goppo",
)

FOREIGN_HINTS = (
    "arthur conan doyle",
    "agatha christie",
    "edgar allan poe",
    "bram stoker",
    "g. k. chesterton",
    "g.k. chesterton",
    "guy de maupassant",
    "roald dahl",
    "h. p. lovecraft",
    "h.g. wells",
    "alexandre dumas",
    "algernon blackwood",
    "sherlock holmes",
    "hercule poirot",
    "শার্লক হোমস",
    "আগাথা ক্রিস্টি",
    "ব্রাম স্টোকার",
    "আর্থার কোনান ডয়েল",
)

BENGALI_HINTS = (
    "satyajit ray",
    "shirshendu",
    "bibhutibhushan",
    "sunil gangopadhyay",
    "sukumar ray",
    "rabindranath",
    "tarashankar",
    "hemendra kumar",
    "narayan gangopadhyay",
    "bimal kar",
    "samman roy",
    "syed mustafa siraj",
    "সত্যজিৎ রায়",
    "সত্যজিৎ রায়",
    "রবীন্দ্রনাথ",
    "বিভূতিভূষণ",
    "শীর্ষেন্দু",
    "সুকুমার রায়",
    "সুনীল গঙ্গোপাধ্যায়",
    "সম্মান রায়",
)


def playable(item):
    url = item.get("audio_url", "")

    if not isinstance(url, str):
        return False

    parts = urlsplit(url)

    return (
        parts.scheme == "https"
        and bool(parts.netloc)
        and bool(item.get("title"))
    )


def writer_group(item):
    title = str(
        item.get("title", "")
    ).casefold()

    foreign = any(
        name in title for name in FOREIGN_HINTS
    )

    bengali = any(
        name in title for name in BENGALI_HINTS
    )

    if foreign and not bengali:
        return "foreign"

    if bengali and not foreign:
        return "bengali"

    return "misc"


def make_queue(episodes):
    groups = {
        kind: {
            source: deque()
            for source in SOURCE_ORDER
        }
        for kind in (
            "bengali",
            "foreign",
            "misc",
        )
    }

    seen_urls = set()

    for item in episodes:
        if not isinstance(item, dict):
            continue

        if not playable(item):
            continue

        source = item.get("source")

        if source not in SOURCE_ORDER:
            continue

        url = item["audio_url"]

        if url in seen_urls:
            continue

        seen_urls.add(url)

        entry = dict(item)

        kind = writer_group(item)

        entry["writer_group"] = kind

        groups[kind][source].append(entry)

    bucket_order = (
        "bengali",
        "foreign",
        "bengali",
        "foreign",
        "misc",
    )

    result = []
    slot = 0
    source_cursor = 0

    def remaining():
        return any(
            groups[kind][source]
            for kind in groups
            for source in SOURCE_ORDER
        )

    while remaining():
        wanted = bucket_order[
            slot % len(bucket_order)
        ]

        priorities = (wanted,) + tuple(
            kind
            for kind in (
                "bengali",
                "foreign",
                "misc",
            )
            if kind != wanted
        )

        chosen = None
        chosen_source_index = None

        for kind in priorities:
            for distance in range(
                len(SOURCE_ORDER)
            ):
                idx = (
                    source_cursor + distance
                ) % len(SOURCE_ORDER)

                source = SOURCE_ORDER[idx]

                if groups[kind][source]:
                    chosen = groups[
                        kind
                    ][source].popleft()

                    chosen_source_index = idx
                    break

            if chosen is not None:
                break

        if chosen is None:
            break

        result.append(chosen)

        source_cursor = (
            chosen_source_index + 1
        ) % len(SOURCE_ORDER)

        slot += 1

    for i, item in enumerate(result):
        item["next_queue_index"] = (
            i + 1
        ) % len(result)

    return result


def main():
    data = json.loads(
        CATALOG.read_text(
            encoding="utf-8-sig"
        )
    )

    records = make_queue(
        data.get("episodes", [])
    )

    if not records:
        raise RuntimeError(
            "No playable podcast episodes"
        )

    output = {
        "schema_version": 1,
        "mode": "podcast_story_rotation",
        "source_order": list(SOURCE_ORDER),
        "total": len(records),
        "play_order": (
            "bengali_foreign_"
            "bengali_foreign_misc_"
            "best_effort"
        ),
        "unknown_writer": (
            "misc_included_and_"
            "repeats_next_cycle"
        ),
        "episodes": records,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        "STORY ROTATION BUILD PASS:",
        len(records),
        "episodes"
    )

    print(
        "Writer groups:",
        {
            group: sum(
                episode["writer_group"] == group
                for episode in records
            )
            for group in (
                "bengali",
                "foreign",
                "misc"
            )
        }
    )

    print(
        "Existing device catalog: UNCHANGED"
    )

    print(
        "ESP32 playback: NOT YET VERIFIED"
    )


if __name__ == "__main__":
    main()
