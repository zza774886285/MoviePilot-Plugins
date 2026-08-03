"""聚影网页搜索客户端"""
import requests
import logging
from typing import Optional, List, Dict

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

    def login(self) -> bool:
        """登录聚影获取token"""
        try:
            resp = self._session.post(f"{self.base_url}/api/login", json={
                "username": self.username, "password": self.password
            }, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token", "")
                return bool(self._token)
        except Exception as e:
            logger.error(f"聚影登录失败: {e}")
        return False

    @property
    def is_ready(self) -> bool:
        """检查是否已准备好（已登录有token）"""
        return bool(self._token)

    def search_resources(self, keyword: str, page: int = 1) -> List[Dict]:
        """搜索资源（token 过期自动重登）"""
        if not self._token:
            if not self.login():
                return []

        for attempt in range(2):  # 首次 + 401 重试一次
            try:
                resp = self._session.post(f"{self.base_url}/api/search", json={
                    "keyword": keyword, "page": page
                }, headers={"Authorization": f"Bearer {self._token}"}, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("resources", [])
                    results = []
                    for r in raw:
                        share_link = r.get("share_link", "") or r.get("url", "")
                        title = r.get("title", "")
                        if share_link:
                            results.append({
                                "url": share_link,
                                "title": title,
                                "update_time": r.get("update_time", "")
                            })
                    return results

                if resp.status_code == 401 and attempt == 0:
                    logger.warning("聚影 token 已过期，尝试重新登录...")
                    if self.login():
                        continue
                    logger.error("聚影重新登录失败")
                    return []

            except Exception as e:
                logger.error(f"聚影搜索失败: {e}")
                return []

        return []

    def check_connection(self) -> dict:
        """检查连接"""
        if not self._token:
            if not self.login():
                return {"status": False, "message": "登录失败"}
        return {"status": True, "message": "连接成功"}
