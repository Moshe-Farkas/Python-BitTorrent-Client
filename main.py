import asyncio
import urllib.parse
from sys import argv
from torrent import Torrent
import requests
from bcoding import bdecode
from torrent_session import TorrentSession


#todo remove
from peer import Peer

import bencoder
import bencodepy



def build_tracker_url(torrent):
    port = 6881
    params = {
        'info_hash': torrent.info_hash,
        'peer_id': torrent.my_peer_id,
        'port': port,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent.file_size
    }
    return torrent.tracker_base_url + '?' + urllib.parse.urlencode(params)


async def init_peers(peers_list, torrent):
    print('num of peers: ', len(peers_list))
    peers_coros = []
    for peer_dict in peers_list:
        peer = Peer(peer_dict['ip'], peer_dict['port'], torrent)

        torrent.temp_add_peer(peer)

        peers_coros.append(peer.download())

    asyncio.ensure_future(torrent.file_saver.start())
    await asyncio.gather(*peers_coros)


if __name__ == '__main__':
    torrent_info = Torrent(argv[1])
    torrent_session = TorrentSession(torrent_info)
    asyncio.run(torrent_session.start_session())
    print('----- exited gracefully -----')

    # torrent.temp_print_torrent_info()
    # url = build_tracker_url(torrent)
    # response_from_tracker = requests.get(url)
    # decoded_response = bdecode(response_from_tracker.text.encode('utf-8'))
    # decoded_response = bdecode(response_from_tracker.content)

    # asyncio.run(init_peers(decoded_response['peers'], torrent))
