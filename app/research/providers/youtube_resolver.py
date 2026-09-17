"""Resolve public YouTube handles and URLs to stable channel IDs."""
import ipaddress
import re
import socket
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

CHANNEL_ID_RE=re.compile(r"(?:channelId|externalId)\"\s*[:=]\s*\"(UC[a-zA-Z0-9_-]{20,})\"")
PLAIN_CHANNEL_ID_RE=re.compile(r"\b(UC[a-zA-Z0-9_-]{20,})\b")
ALLOWED_HOSTS={"youtube.com","www.youtube.com","m.youtube.com"}

def _normalize_source(source:str)->str:
    value=source.strip()
    if not value: raise ValueError("YouTube channel cannot be empty")
    if value.startswith("UC") and PLAIN_CHANNEL_ID_RE.fullmatch(value): return value
    if value.startswith("@"): return f"https://www.youtube.com/{quote(value,safe='@')}/about"
    if not value.startswith(("http://","https://")): return f"https://www.youtube.com/@{quote(value.lstrip('@'),safe='')}/about"
    parsed=urlparse(value)
    if parsed.scheme.lower()!="https" or parsed.hostname not in ALLOWED_HOSTS: raise ValueError("Only public HTTPS YouTube URLs are allowed")
    path=parsed.path.rstrip("/")
    return f"https://www.youtube.com{path if path.endswith('/about') else path+'/about'}"

def _assert_public_host(hostname:str)->None:
    try:
        addresses=socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)
    except socket.gaierror as exc: raise ValueError("Could not resolve YouTube host") from exc
    for item in addresses:
        address=item[4][0]
        ip=ipaddress.ip_address(address)
        if not ip.is_global: raise ValueError("Refusing non-public network destination")

def resolve_channel_id(source:str,*,timeout:int=10)->str:
    normalized=_normalize_source(source)
    if normalized.startswith("UC") and PLAIN_CHANNEL_ID_RE.fullmatch(normalized): return normalized
    host=urlparse(normalized).hostname
    if host not in ALLOWED_HOSTS: raise ValueError("Only public YouTube hosts are allowed")
    _assert_public_host(host)
    request=Request(normalized,headers={"User-Agent":"ContentOS/1.0"})
    with urlopen(request,timeout=timeout) as response:
        if response.geturl() and urlparse(response.geturl()).hostname not in ALLOWED_HOSTS: raise ValueError("Unexpected redirect outside YouTube")
        html=response.read().decode("utf-8",errors="replace")
    match=CHANNEL_ID_RE.search(html) or PLAIN_CHANNEL_ID_RE.search(html)
    if not match: raise ValueError(f"Could not resolve a YouTube channel ID from: {source}")
    return match.group(1)

def resolve_channel_ids(sources:list[str],*,timeout:int=10)->list[str]:
    resolved=[]; seen=set()
    for source in sources:
        channel_id=resolve_channel_id(source,timeout=timeout)
        if channel_id not in seen: seen.add(channel_id); resolved.append(channel_id)
    return resolved
