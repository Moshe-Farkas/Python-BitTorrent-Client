import asyncio
from sys import argv
from torrent import Torrent
from torrent_session import TorrentSession


if __name__ == '__main__':
    # argv.append('torrent-files/debian.torrent')
    argv.append('torrent-files/doom64.torrent')
    # argv.append('torrent-files/ubuntu.torrent')

    torrent_info = Torrent(argv[1])
    torrent_session = TorrentSession(torrent_info)

    asyncio.run(torrent_session.start_session())
    print('----- exited gracefully -----')

