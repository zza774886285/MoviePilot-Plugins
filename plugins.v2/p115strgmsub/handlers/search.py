"""
搜索处理模块
负责所有搜索相关逻辑：JuyingWeb、Nullbr、PanSou
"""
from typing import Optional, List, Dict, Any

from app.core.config import settings
from app.log import logger
from app.schemas import MediaInfo
from app.schemas.types import MediaType

from ..utils import convert_nullbr_to_pansou_format


class SearchHandler:
    """搜索处理器"""

    def __init__(
        self,
        pansou_client,
        nullbr_client,
        juying_client,
        pansou_enabled: bool = False,
        nullbr_enabled: bool = False,
        juying_enabled: bool = False,
        juying_username: str = "",
        juying_password: str = "",
        only_115: bool = True,
        pansou_channels: str = "",
        search_source_order: Optional[List[str]] = None
    ):
        """
        初始化搜索处理器

        :param pansou_client: PanSou 客户端实例
        :param nullbr_client: Nullbr 客户端实例
        :param juying_client: JuyingWeb 客户端实例
        :param pansou_enabled: 是否启用 PanSou
        :param nullbr_enabled: 是否启用 Nullbr
        :param juying_enabled: 是否启用 JuyingWeb
        :param juying_username: 聚影用户名
        :param juying_password: 聚影密码
        :param only_115: 是否只搜索115网盘资源
        :param pansou_channels: PanSou 搜索频道
        :param search_source_order: 自定义搜索源优先级列表，如 ["pansou", "juying"]；
                                    为空时使用默认优先级 Nullbr > JuyingWeb > PanSou
        """
        self._pansou_client = pansou_client
        self._nullbr_client = nullbr_client
        self._juying_client = juying_client
        self._pansou_enabled = pansou_enabled
        self._nullbr_enabled = nullbr_enabled
        self._juying_enabled = juying_enabled
        self._juying_username = juying_username
        self._juying_password = juying_password
        self._only_115 = only_115
        self._pansou_channels = pansou_channels
        self._search_source_order = search_source_order or []

    def get_enabled_sources(self) -> List[str]:
        """
        获取已启用且可用的搜索源列表，按优先级排序

        优先级规则：
        1. 用户配置了自定义优先级（search_source_order）时按其顺序排列；
           未出现在自定义列表中的已启用源按默认顺序追加在末尾
        2. 未配置时使用默认优先级 Nullbr > JuyingWeb > PanSou

        :return: 搜索源名称列表
        """
        # 按默认优先级收集已启用且可用的源
        available = []

        # Nullbr
        if self._nullbr_enabled and self._nullbr_client:
            available.append("nullbr")

        # JuyingWeb
        if self._juying_enabled and self._juying_username and self._juying_password:
            available.append("juying")

        # PanSou
        if self._pansou_enabled and self._pansou_client:
            available.append("pansou")

        # 应用用户自定义优先级
        if self._search_source_order:
            sources = [s for s in self._search_source_order if s in available]
            sources += [s for s in available if s not in sources]
            return sources

        return available

    def search_resources(
        self,
        mediainfo: MediaInfo,
        media_type: MediaType,
        season: Optional[int] = None
    ) -> List[Dict]:
        """
        统一的资源搜索方法，支持电影和电视剧
        按优先级尝试所有启用的搜索源，第一个有结果的就返回
        搜索优先级: 默认 Nullbr > JuyingWeb > PanSou，支持通过配置自定义排序

        注意：此方法主要供电影订阅使用。电视剧订阅使用 search_single_source 进行逐源搜索。

        :param mediainfo: 媒体信息
        :param media_type: 媒体类型（MOVIE 或 TV）
        :param season: 季号（电视剧必需）
        :return: 115网盘资源列表
        """
        sources = self.get_enabled_sources()

        for source in sources:
            results = self.search_single_source(source, mediainfo, media_type, season)
            if results:
                return results
            else:
                # 打印回退日志
                remaining = sources[sources.index(source) + 1:]
                if remaining:
                    logger.info(f"{source.capitalize()} 未找到资源，将回退到 {'/'.join([s.capitalize() for s in remaining])} 搜索")

        return []

    def search_single_source(
        self,
        source: str,
        mediainfo: MediaInfo,
        media_type: MediaType,
        season: Optional[int] = None
    ) -> List[Dict]:
        """
        使用指定的单一搜索源查询资源

        :param source: 搜索源名称 ("nullbr", "juying", "pansou")
        :param mediainfo: 媒体信息
        :param media_type: 媒体类型
        :param season: 季号（电视剧时使用）
        :return: 115网盘资源列表
        """
        if source == "nullbr":
            return self._search_nullbr(mediainfo, media_type, season)
        elif source == "juying":
            return self._search_juying(mediainfo, media_type, season)
        elif source == "pansou":
            if media_type == MediaType.MOVIE:
                return self._search_pansou_movie(mediainfo)
            else:
                return self._search_pansou_tv(mediainfo, season)
        else:
            logger.warning(f"未知的搜索源: {source}")
            return []

    def _pansou_search(self, keyword: str) -> List[Dict]:
        """
        PanSou 搜索的通用逻辑

        :param keyword: 搜索关键词
        :return: 115网盘资源列表
        """
        cloud_types = ["115"] if self._only_115 else None

        channels = None
        if self._pansou_channels and self._pansou_channels.strip():
            channels = [ch.strip() for ch in self._pansou_channels.split(',') if ch.strip()]

        search_results = self._pansou_client.search(
            keyword=keyword,
            cloud_types=cloud_types,
            channels=channels,
            limit=20
        )

        results = search_results.get("results", {}) if search_results and not search_results.get("error") else {}
        return results.get("115网盘", [])

    def _search_nullbr(
        self,
        mediainfo: MediaInfo,
        media_type: MediaType,
        season: Optional[int] = None
    ) -> List[Dict]:
        """
        仅使用 Nullbr 搜索资源

        :param mediainfo: 媒体信息
        :param media_type: 媒体类型（MOVIE 或 TV）
        :param season: 季号（电视剧时使用）
        :return: 115网盘资源列表
        """
        if not self._nullbr_client:
            logger.warning(f"Nullbr 客户端未初始化，跳过 Nullbr 查询")
            return []

        if not mediainfo.tmdb_id:
            logger.warning(f"{mediainfo.title} 缺少 TMDB ID，无法使用 Nullbr 查询")
            return []

        if media_type == MediaType.MOVIE:
            logger.info(f"使用 Nullbr 查询电影资源: {mediainfo.title} (TMDB ID: {mediainfo.tmdb_id})")
            nullbr_resources = self._nullbr_client.get_movie_resources(mediainfo.tmdb_id)
        else:  # MediaType.TV
            logger.info(f"使用 Nullbr 查询电视剧资源: {mediainfo.title} S{season} (TMDB ID: {mediainfo.tmdb_id})")
            nullbr_resources = self._nullbr_client.get_tv_resources(mediainfo.tmdb_id, season)

        if nullbr_resources:
            results = convert_nullbr_to_pansou_format(nullbr_resources)
            logger.info(f"Nullbr 找到 {len(results)} 个资源")
            return results

        logger.info(f"Nullbr 未找到资源")
        return []

    def _search_pansou_movie(
        self,
        mediainfo: MediaInfo,
    ) -> List[Dict]:
        """
        仅使用 PanSou 搜索电影资源（带降级关键词策略）

        :param mediainfo: 媒体信息
        :return: 115网盘资源列表
        """
        if not self._pansou_client:
            logger.warning(f"PanSou 客户端未初始化，跳过 PanSou 查询")
            return []

        # 电影使用降级搜索策略
        search_keywords = [
            f"{mediainfo.title} {mediainfo.year}",
            mediainfo.title
        ]

        for keyword in search_keywords:
            logger.info(f"使用 PanSou 搜索电影资源: {mediainfo.title}，关键词: '{keyword}'")
            results = self._pansou_search(keyword)
            if results:
                logger.info(f"PanSou 关键词 '{keyword}' 搜索到 {len(results)} 个结果")
                return results
            else:
                logger.info(f"PanSou 关键词 '{keyword}' 无结果，尝试下一个降级关键词")

        logger.info(f"PanSou 未找到资源")
        return []

    def _search_pansou_tv(
        self,
        mediainfo: MediaInfo,
        season: int
    ) -> List[Dict]:
        """
        仅使用 PanSou 搜索电视剧资源（带降级关键词策略）

        :param mediainfo: 媒体信息
        :param season: 季号
        :return: 115网盘资源列表
        """
        if not self._pansou_client:
            logger.warning(f"PanSou 客户端未初始化，跳过 PanSou 查询")
            return []

        # 电视剧使用降级搜索策略
        search_keywords = [
            f"{mediainfo.title}{season}",  # 中文季号格式
            mediainfo.title
        ]

        for keyword in search_keywords:
            logger.info(f"使用 PanSou 搜索电视剧资源: {mediainfo.title} S{season}，关键词: '{keyword}'")
            results = self._pansou_search(keyword)
            if results:
                logger.info(f"PanSou 关键词 '{keyword}' 搜索到 {len(results)} 个结果")
                return results
            else:
                logger.info(f"PanSou 关键词 '{keyword}' 无结果，尝试下一个降级关键词")

        logger.info(f"PanSou 未找到资源")
        return []

    def _search_juying(
        self,
        mediainfo: MediaInfo,
        media_type: MediaType,
        season: Optional[int] = None
    ) -> List[Dict]:
        """
        使用 JuyingWeb 搜索资源

        :param mediainfo: 媒体信息
        :param media_type: 媒体类型（MOVIE 或 TV）
        :param season: 季号（电视剧时使用）
        :return: 115网盘资源列表
        """
        if not self._juying_client:
            logger.warning("JuyingWeb 客户端未初始化，跳过查询")
            return []

        if not self._juying_username or not self._juying_password:
            logger.warning("JuyingWeb 需要配置用户名和密码")
            return []

        # 构建搜索关键词
        if media_type == MediaType.MOVIE:
            keyword = f"{mediainfo.title} {mediainfo.year}" if mediainfo.year else mediainfo.title
        else:
            keyword = f"{mediainfo.title} S{season}" if season else mediainfo.title

        logger.info(f"使用 JuyingWeb 查询: {keyword} (TMDB ID: {mediainfo.tmdb_id})")

        try:
            results = self._juying_client.search_resources(keyword)
            if results:
                logger.info(f"JuyingWeb 找到 {len(results)} 个资源")
                return results
            logger.info(f"JuyingWeb 未找到资源")
        except Exception as e:
            logger.error(f"JuyingWeb 查询失败: {e}")

        return []
