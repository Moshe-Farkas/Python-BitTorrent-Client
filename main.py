import asyncio
from sys import argv
from torrent import Torrent
from torrent_session import TorrentSession
from datetime import datetime


if __name__ == '__main__':
    # argv.append('torrent-files/debian.torrent')
    # argv.append('torrent-files/doom64.torrent')
    # argv.append('torrent-files/ubuntu.torrent')
    argv.append('torrent-files/partion-master.torrent')
    # argv.append('torrent-files/revo.torrent')
    # argv.append('torrent-files/gemstone.torrent')

    torrent_info = Torrent(argv[1])
    torrent_session = TorrentSession(torrent_info)

    start_time = datetime.now()
    asyncio.run(torrent_session.start_session())
    end_date_time = datetime.now() - start_time
    hours = end_date_time.seconds // (60 * 60)
    minutes = end_date_time.seconds // 60
    seconds = end_date_time.seconds % 60
    print(f'finished in {hours} hours, {minutes} minutes and {seconds} seconds')

