BitTorrent client written in python using pythons asyncio framework.
The project uses a producer consumer architecture. Producers downloads pieces while a consumer consumes it via an asyncio Queue to write them to disk.

### Usage:
    pip install -r requirements.txt
    py torr-client.py path/to/file.torrent

