import asyncio
import os
import sys
import urllib.parse
from sys import argv

import bitstring

from torrent import Torrent
import requests
from bcoding import bdecode
from piece import Piece
from peer import Peer


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
    peers_coros = []
    for peer_dict in peers_list:
        peer = Peer(peer_dict['ip'], peer_dict['port'], torrent)

        torrent.temp_add_peer(peer)

        peers_coros.append(peer.download())
    await asyncio.gather(*peers_coros)


if __name__ == '__main__':
    torrent = Torrent(argv[1])
    Piece.PIECE_LENGTH = torrent.piece_length
    url = build_tracker_url(torrent)
    response_from_tracker = requests.get(url)
    decoded_response = bdecode(response_from_tracker.text)
    torrent.temp_print_torrent_info()

    asyncio.run(init_peers(decoded_response['peers'], torrent))
