from app.research.engine import normalize_items
from app.research.providers.youtube_rss import parse_youtube_feed


FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <title>Example Channel</title>
  <entry>
    <id>yt:video:abc123</id>
    <yt:videoId>abc123</yt:videoId>
    <title>  AI  Workflow  Update </title>
    <published>2026-09-17T10:00:00+00:00</published>
    <author><name>Example Channel</name></author>
    <media:group><media:description>New workflow research.</media:description></media:group>
  </entry>
</feed>'''


def test_parse_youtube_feed():
    items = parse_youtube_feed(FEED)
    assert len(items) == 1
    assert items[0].title == "AI Workflow Update"
    assert str(items[0].url).endswith("abc123")
    assert items[0].source_name == "YouTube — Example Channel"


def test_normalize_research_deduplicates_urls():
    items = parse_youtube_feed(FEED)
    assert len(normalize_items(items + items)) == 1
