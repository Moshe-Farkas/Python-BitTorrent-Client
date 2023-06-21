from torrent import Torrent


class TorrentSession:
    def __init__(self, torrent_info: Torrent):
        self._torrent_info = torrent_info
        self._completed_pieces = 0
        self._currently_downloading_peers = []

    async def start_session(self):
        while not self.complete():
            # get_tracker_response()
            # run_coros(response.peers) # non blocking. needs to add new peers only
            # await sleep(interval_time)

            pass

    def complete(self):
        return self._completed_pieces == self._torrent_info.num_of_pieces

