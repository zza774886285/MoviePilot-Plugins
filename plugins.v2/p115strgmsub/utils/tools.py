"""
工具函数模块
包含不涉及业务逻辑的通用工具函数
"""
import base64
import datetime
import json
import os
import platform
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Any, List, Dict, Tuple

from app.core.config import settings
from app.log import logger

def _parse_proxy_url(proxy) -> Optional[Dict[str, str]]:
    """
    解析代理URL，支持 http://user:password@ip:port 格式
    
    :param proxy: 代理配置，可以是字符串或字典
    :return: Playwright 格式的代理配置 {"server": "...", "username": "...", "password": "..."}
    """
    if not proxy:
        return None
    
    # 如果是字典格式，取 http 或 https
    if isinstance(proxy, dict):
        proxy_url = proxy.get("http") or proxy.get("https")
    else:
        proxy_url = str(proxy)
    
    if not proxy_url:
        return None
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        
        # 构建不带认证的服务器地址
        if parsed.port:
            server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        else:
            server = f"{parsed.scheme}://{parsed.hostname}"
        
        result = {"server": server}
        
        # 如果有用户名和密码
        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password
        
        return result
    except Exception as e:
        logger.debug(f"解析代理URL失败: {e}，将直接使用原始URL")
        return {"server": proxy_url}

def download_so_file(lib_dir: Path):
    """
    确保依赖库目录存在
    """
    lib_dir.mkdir(parents=True, exist_ok=True)

def decode_jwt_payload(token: str) -> Optional[dict]:
    """
    解码 JWT token 的 payload 部分（不验证签名）

    :param token: JWT token 字符串
    :return: payload 字典，解码失败返回 None
    """
    if not token:
        return None

    try:
        # JWT 格式: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # 解码 payload（第二部分）
        payload = parts[1]
        # 补齐 base64 padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        logger.debug(f"解码 JWT 失败: {e}")
        return None

def convert__to_pansou_format(_resources: List[Dict]) -> List[Dict]:
    """

    统一格式: {"url": "...", "title": "...", "update_time": ""}

    :return: 统一格式的资源列表
    """
    converted = []
    for resource in _resources:
        converted.append({
            "url": resource.get("share_link", ""),
            "title": resource.get("title", ""),
            "update_time": ""          })
    return converted
