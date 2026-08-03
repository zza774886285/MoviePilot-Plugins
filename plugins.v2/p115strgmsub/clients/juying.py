"""聚影网页搜索客户端
基于 MediaSync115 的 JuyingWebService 实现
"""
import re
import logging
from typing import Optional, List, Dict

import requests

logger = logging.getLogger(__name__)


class JuyingWebClient:
    """聚影网页搜索客户端"""

    def __init__(self, username: str = "", password: str = "",
                 base_url: str = "https://www.jying.top", proxy: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self._token = ""
        self._session = requests.Session()
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "MoviePilot-JuyingWeb/1.0",
        })

    def _csrf_headers(self) -> dict:
        token = str(self._session.cookies.get("csrftoken") or "")
        headers = {"Origin": self.base_url, "Referer": f"{self.base_url}/"}
        if token:
            headers["X-CSRFToken"] = token
        return headers

    def login(self) -> bool:
        try:
            csrf_resp = self._session.get(f"{self.base_url}/api/csrf/", timeout=30)
            if csrf_resp.status_code != 200:
                return False
            resp = self._session.post(
                f"{self.base_url}/api/app/login/",
                json={"username": self.username, "password": self.password},
                headers=self._csrf_headers(), timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = str(data.get("token") or "").strip()
                return bool(self._token)
        except Exception as e:
            logger.error(f"聚影登录异常: {e}")
        return False

    @property
    def is_ready(self) -> bool:
        return bool(self._token)

    def _request(self, method: str, path: str, **kwargs) -> Optional[dict]:
        for attempt in range(2):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.update(self._csrf_headers())
            if self._token:
                headers["X-App-User-Token"] = self._token
            try:
                resp = self._session.request(
                    method, f"{self.base_url}{path}", headers=headers, timeout=30, **kwargs
                )
                refreshed = str(resp.headers.get("x-refreshed-token") or "").strip()
                if refreshed:
                    self._token = refreshed
                if resp.status_code == 200:
                    if "application/json" in str(resp.headers.get("content-type") or "").lower():
                        return resp.json()
                    return None
                if resp.status_code == 401 and attempt == 0:
                    self._token = ""
                    if self.login():
                        continue
                    return None
                if resp.status_code == 429:
                    return None
                return None
            except Exception as e:
                logger.error(f"聚影请求异常: {e}")
                return None
        return None

    def search_resources(self, keyword: str) -> List[Dict]:
        if not self._token and not self.login():
            return []
        payload = self._request("GET", "/api/app/movies/", params={
            "q": keyword, "page": 1, "page_size": 30,
        })
        if not payload:
            return []
        rows = payload.get("results") or []
        candidates = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
        if not candidates:
            return []
        movie = candidates[0]
        movie_id = movie.get("id")
        if not movie_id:
            return []
        return self._get_movie_resources(movie_id)

    def _get_movie_resources(self, movie_id: int) -> List[Dict]:
        results, seen_ids = [], set()
        for page in range(1, 11):
            page_size = 120 if page == 1 else 200
            payload = self._request(
                "GET", f"/api/app/movie/{movie_id}/resources/",
                params={"page": page, "page_size": page_size},
            )
            if not payload:
                break
            rows = payload.get("resources") or []
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("id") or "").strip()
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)
                if str(row.get("resource_type") or "").strip().lower() != "115":
                    continue
                share_link = str(row.get("share_link") or "").strip()
                if share_link:
                    results.append({
                        "url": share_link,
                        "title": str(row.get("title") or "").strip(),
                        "update_time": str(row.get("update_time") or ""),
                    })
            if not payload.get("has_more"):
                break
        return results

    def check_connection(self) -> dict:
        if not self._token and not self.login():
            return {"status": False, "message": "登录失败"}
        return {"status": True, "message": "连接成功"}