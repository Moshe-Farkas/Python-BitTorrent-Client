import urllib.parse
import requests
import socket
from bencode import bdecode
import struct
import random


def peer_gen(urls, torrent_info):
    for url in urls:
        if url.startswith('http'):
            yield http_tracker(url, torrent_info)
        elif url.startswith('udp'):
            yield udp_tracker(url, torrent_info)


def http_tracker(announce_url, torrent_info):
    port = 6881
    params = {
        'info_hash': torrent_info.info_hash,
        'peer_id': torrent_info.my_peer_id,
        'port': port,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent_info.total_torrent_length
    }
    url = announce_url + '?' + urllib.parse.urlencode(params)
    encoded_response = requests.get(url, timeout=5.0)
    if encoded_response.status_code != 200:
        return []
    decoded_response = bdecode(encoded_response.content)
    return decoded_response['peers']


def udp_tracker(announce_url, torrent_info):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    connect_message = build_udp_connect_request()
    parsed_url = urllib.parse.urlparse(announce_url)
    try:
        sock.sendto(connect_message, (parsed_url.hostname, parsed_url.port))
        response = sock.recv(16)
        connection_id = parse_udp_connect_response(response)
        announce_request = build_udp_announce_request(
            connection_id,
            torrent_info.my_peer_id,
            torrent_info.info_hash,
            torrent_info.total_torrent_length
        )
        sock.sendto(announce_request, (parsed_url.hostname, parsed_url.port))
        response = sock.recv(4096)
        return parse_udp_announce_response(response)
    except ConnectionError:
        return []
    except TimeoutError:
        return []
    except socket.gaierror:
        return []


def build_udp_connect_request():
    # Offset  Size            Name            Value
    # 0       64-bit integer  connection_id   0x41727101980
    # 8       32-bit integer  action          0 // connect
    # 12      32-bit integer  transaction_id  ? // random
    # 16
    protocol_id = struct.pack('>Q', 0x41727101980)
    action = struct.pack('>I', 0)
    transaction_id = bytes(random.getrandbits(8) for _ in range(4))
    return protocol_id + action + transaction_id


def parse_udp_connect_response(message):
    # Offset  Size            Name               Value
    # 0       32-bit integer  action             0 // connect
    # 4       32-bit integer  transaction_id
    # 8      64-bit integer  connection_id
    # 16
    return message[8:]


def build_udp_announce_request(connection_id, peer_id, info_hash, total_length):
    # Offset  Size    Name    Value
    # 0       64-bit integer  connection_id
    # 8       32-bit integer  action          1 // announce
    # 12      32-bit integer  transaction_id
    # 16      20-byte string  info_hash
    # 36      20-byte string  peer_id
    # 56      64-bit integer  downloaded
    # 64      64-bit integer  left
    # 72      64-bit integer  uploaded
    # 80      32-bit integer  event           0 // 0: none; 1: completed; 2: started; 3: stopped
    # 84      32-bit integer  IP address      0 // default
    # 88      32-bit integer  key             ? // random
    # 92      32-bit integer  num_want        -1 // default
    # 96      16-bit integer  port            ? //
    # 98
    action = struct.pack('>I', 1)
    transaction_id = bytes(random.getrandbits(8) for _ in range(4))
    to_download = total_length
    downloaded = struct.pack('>Q', to_download)
    left = struct.pack('>Q', total_length - to_download)
    uploaded = struct.pack('>Q', 0)
    event = struct.pack('>I', 0)
    ip = struct.pack('>I', 0)
    key = bytes(random.getrandbits(8) for _ in range(4))
    want = struct.pack('>i', -1)
    port = struct.pack('>H', 6881)

    return (
            connection_id + action + transaction_id + info_hash +
            peer_id + downloaded + left + uploaded + event +
            ip + key + want + port
    )


def parse_udp_announce_response(response):
    #  Offset      Size            Name            Value
    # 0           32-bit integer  action          1 // announce
    # 4           32-bit integer  transaction_id
    # 8           32-bit integer  interval
    # 12          32-bit integer  leechers
    # 16          32-bit integer  seeders
    # 20 + 6 * n  32-bit integer  IP address
    # 24 + 6 * n  16-bit integer  TCP port
    # 20 + 6 * N
    ips = response[20:]
    peers = []
    for i in range(0, len(ips), 6):
        peer_ip, peer_port = struct.unpack('>IH', ips[i: i+6])
        # peers.append(
        #     {'ip': str(ipaddress.IPv4Address(peer_ip)), 'port': peer_port}
        # )
        peers.append(
            {'ip': socket.inet_ntoa(ips[i: i+4]), 'port': peer_port}
        )
    return peers

