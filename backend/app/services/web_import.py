import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("只支持 http:// 或 https:// 网页地址")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ValueError("不允许访问本机地址")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("网页地址无法解析") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("不允许访问内网或本机地址")


def fetch_webpage(url: str, output_path: Path) -> tuple[str, str]:
    validate_public_url(url)
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": "PersonalKnowledgeAgent/0.1"}) as client:
        response = client.get(url)
        response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise ValueError("目标地址不是 HTML 网页")
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "nav", "footer", "form", "aside"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = " ".join(main.get_text(" ", strip=True).split())
    if len(text) < 50:
        raise ValueError("网页正文内容过少，无法建立知识库索引")
    output_path.write_text(text, encoding="utf-8")
    return title[:255], text
