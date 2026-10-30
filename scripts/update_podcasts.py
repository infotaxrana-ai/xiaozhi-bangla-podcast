import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "podcasts.json"

def clean(text):
    text = re.sub(r"<[^>]*>", " ", text or "")
    return " ".join(text.split())

def valid_url(url):
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and bool(p.netloc)

def main():
    config = json.loads(
        (ROOT / "sources.json").read_text(encoding="utf-8-sig")
    )

    episodes = []
    status = []
    seen = set()
    successful_feeds = 0

    for source in config["sources"]:
        if not source.get("enabled"):
            continue

        rss = source.get("rss", "")
        if not valid_url(rss):
            status.append({
                "source": source["id"],
                "status": "invalid_feed"
            })
            continue

        try:
            request = urllib.request.Request(
                rss,
                headers={"User-Agent": "XiaozhiPodcast/1.0"}
            )

            with urllib.request.urlopen(
                request, timeout=30
            ) as response:
                xml_data = response.read(5_000_000)

            root = ET.fromstring(xml_data)
            items = root.findall(".//channel/item")
            count = 0
            successful_feeds += 1

            for item in items[:100]:
                enclosure = item.find("enclosure")
                if enclosure is None:
                    continue

                url = enclosure.get("url", "")
                media_type = enclosure.get("type", "").lower()

                if not valid_url(url):
                    continue

                if media_type and not (
                    media_type.startswith("audio/")
                    or media_type == "application/octet-stream"
                ):
                    continue

                if url in seen:
                    continue

                seen.add(url)
                count += 1

                episodes.append({
                    "id": source["id"] + "_" + str(count),
                    "source": source["id"],
                    "podcast": source["name"],
                    "category": source["category"],
                    "title": clean(item.findtext("title")),
                    "description": clean(
                        item.findtext("description")
                    )[:350],
                    "audio_url": url,
                    "audio_type": media_type,
                    "published": item.findtext("pubDate") or "",
                    "device_verified": False
                })

            status.append({
                "source": source["id"],
                "status": "fetched",
                "episodes": count
            })

        except Exception as e:
            status.append({
                "source": source["id"],
                "status": "error",
                "message": str(e)[:160]
            })

    if successful_feeds == 0:
        print("WARNING: No feed fetched successfully.")
        print(json.dumps(status, ensure_ascii=False))
        return

    result = {
        "schema_version": 1,
        "feature": "xiaozhi_podcast_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(episodes),
        "sources": status,
        "episodes": episodes
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("PODCAST RSS COLLECTOR PASS")
    print("Total episodes:", len(episodes))
    print(json.dumps(status, ensure_ascii=False))

if __name__ == "__main__":
    main()