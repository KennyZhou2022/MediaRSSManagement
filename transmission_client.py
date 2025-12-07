import requests


class TransmissionClient:
    def __init__(self, url, username="", password=""):
        self.url = url
        self.auth = (username, password) if username else None
        self.session_id = None

    def _rpc(self, method, arguments=None):
        if arguments is None:
            arguments = {}

        headers = {}
        if self.session_id:
            headers["X-Transmission-Session-Id"] = self.session_id

        payload = {
            "method": method,
            "arguments": arguments
        }

        resp = requests.post(self.url, json=payload, headers=headers, auth=self.auth)

        # Session-id missing → resend
        if resp.status_code == 409:
            self.session_id = resp.headers["X-Transmission-Session-Id"]
            headers["X-Transmission-Session-Id"] = self.session_id
            resp = requests.post(self.url, json=payload, headers=headers, auth=self.auth)

        return resp.json()

    def add_torrent(self, torrent_url):
        try:
            res = self._rpc("torrent-add", {"filename": torrent_url})
            return "torrent-added" in res.get("result", "").lower()
        except Exception:
            return False
