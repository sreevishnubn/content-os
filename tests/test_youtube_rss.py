from app.research.providers.youtube_rss import parse_youtube_feed


def test_parse_youtube_feed_extracts_uploads():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015"
          xmlns:media="http://search.yahoo.com/mrss/">
      <title>Example Channel</title>
      <entry>
        <yt:videoId>abc123</yt:videoId>
        <title>AI Automation Demo</title>
        <published>2026-09-18T08:00:00+00:00</published>
        <author><name>Example Channel</name></author>
        <media:group><media:description>Automation description</media:description></media:group>
      </entry>
    </feed>'''
    items = parse_youtube_feed(xml)
    assert len(items) == 1
    assert items[0].title == "AI Automation Demo"
    assert str(items[0].url) == "https://www.youtube.com/watch?v=abc123"


def test_uploads_playlist_id_mapping():
    channel_id = "UCHPowQzQzi9oautiZJFVs4g"
    assert "UU" + channel_id[2:] == "UUHPowQzQzi9oautiZJFVs4g"
