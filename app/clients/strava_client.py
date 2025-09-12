"""
Strava API client with minimal error handling and resolution selection.
"""

from typing import Dict, Any, Optional, List
import logging
import requests

from ..config import STRAVA_TIMEOUT


logger = logging.getLogger(__name__)


class StravaApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Strava API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class StravaClient:
    def __init__(self, access_token: str, timeout: Optional[int] = None):
        self.access_token = access_token
        self.timeout = timeout or STRAVA_TIMEOUT
        self.base_url = "https://www.strava.com/api/v3"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params or {}, timeout=self.timeout)
        if resp.status_code != 200:
            raise StravaApiError(resp.status_code, resp.text)
        return resp.json()

    @staticmethod
    def choose_resolution(moving_time_seconds: int) -> str:
        # Keep the original logic: use medium when duration large to avoid 10k cap issues
        return "medium" if moving_time_seconds and moving_time_seconds > 10000 else "high"

    def get_activity(self, activity_id: int) -> Dict[str, Any]:
        return self._get(f"/activities/{activity_id}")

    def get_athlete(self) -> Dict[str, Any]:
        return self._get("/athlete")

    def get_streams(
        self,
        activity_id: int,
        keys: List[str],
        resolution: str,
        key_by_type: bool = True,
    ) -> Dict[str, Any]:
        params = {
            "keys": ",".join(keys),
            "key_by_type": str(key_by_type).lower(),
            "resolution": resolution,
        }
        return self._get(f"/activities/{activity_id}/streams", params=params)

    def fetch_full(
        self,
        activity_id: int,
        keys: List[str],
        resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        activity = self.get_activity(activity_id)
        moving_time = activity.get("moving_time", 0)
        final_res = resolution or self.choose_resolution(moving_time)
        streams = self.get_streams(activity_id, keys=keys, resolution=final_res, key_by_type=True)
        athlete = self.get_athlete()
        return {
            "activity": activity,
            "streams": streams,
            "athlete": athlete,
            "resolution": final_res,
        }

