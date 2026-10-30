
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/podcast_story_rotation.json"
DEST = ROOT / "data/podcast_pages"

PAGE_SIZE = 4
MAX_PAGE_BYTES = 4096


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    episodes = data["episodes"]
    total = len(episodes)

    assert total == data["total"]
    assert total > 0

    id_index = {e["id"]: i for i, e in enumerate(episodes)}
    assert len(id_index) == total

    heads = [
        i for i, e in enumerate(episodes)
        if i == 0
        or e["story_id"] != episodes[i - 1]["story_id"]
    ]

    # Every entry must follow the exact rotation order.
    for i, ep in enumerate(episodes):
        next_id = (
            ep.get("next_episode_id")
            or ep.get("next_story_id")
        )

        expected = episodes[i + 1]["id"] if i + 1 < total else None

        assert (next_id or None) == expected, (
            f"Broken rotation at {ep['id']}"
        )

    DEST.mkdir(parents=True, exist_ok=True)

    for old in DEST.glob("*.json"):
        old.unlink()

    page_count = (total + PAGE_SIZE - 1) // PAGE_SIZE

    for page in range(page_count):
        start = page * PAGE_SIZE
        selected = episodes[start:start + PAGE_SIZE]

        items = []

        for offset, ep in enumerate(selected):
            ne = ep.get("next_episode_id") or ""
            ns = ep.get("next_story_id") or ""

            items.append({
                "i": start + offset,
                "id": ep["id"],
                "title": ep["title"],
                "url": ep["audio_url"],
                "source": ep["source"],
                "ne": id_index[ne] if ne else -1,
                "ns": id_index[ns] if ns else -1,
            })

        result = {
            "v": 1,
            "total": total,
            "size": PAGE_SIZE,
            "page": page,
            "pages": page_count,
            "items": items,
        }

        if page == 0:
            result["heads"] = heads

        content = json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"

        encoded = content.encode("utf-8")

        if len(encoded) > MAX_PAGE_BYTES:
            raise ValueError(
                f"Page {page} is too large: {len(encoded)} bytes"
            )

        target = DEST / f"{page:03d}.json"
        target.write_bytes(encoded)

    print("PODCAST PAGINATION PASS")
    print("Episodes:", total)
    print("Stories:", len(heads))
    print("Pages:", page_count)
    print("Maximum page size:", MAX_PAGE_BYTES)


if __name__ == "__main__":
    main()
