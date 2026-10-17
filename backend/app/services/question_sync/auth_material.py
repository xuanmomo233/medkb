"""Import an authorized login token or signed request from the existing client protocol."""
import base64
import json
from urllib.parse import parse_qs, urlsplit


def session_value(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or any(c.isspace() for c in value):
        raise ValueError("登录令牌格式无效")
    return value


def decode_request_token(value: str) -> str:
    from Crypto.Cipher import AES
    from Crypto.Hash import MD5

    try:
        outer = base64.b64decode(value, validate=True).decode("utf-8")
        encrypted, stamp = outer.rsplit("#", 1)
        if not stamp.isdigit():
            raise ValueError()
        data = base64.b64decode(encrypted, validate=True)
        if not data.startswith(b"Salted__") or len(data) < 32:
            raise ValueError()
        salt, derived = data[8:16], b""
        while len(derived) < 48:
            derived += MD5.new((derived[-16:] if derived else b"") + b"ixunke" + salt).digest()
        plain = AES.new(derived[:32], AES.MODE_CBC, derived[32:48]).decrypt(data[16:])
        padding = plain[-1]
        if not 1 <= padding <= 16 or plain[-padding:] != bytes([padding]) * padding:
            raise ValueError()
        seed, inner_stamp = plain[:-padding].decode("utf-8").rsplit("#", 1)
        if inner_stamp != stamp:
            raise ValueError()
        return session_value(seed)
    except (ValueError, UnicodeError, IndexError):
        raise ValueError("请求 Token 无法按项目现有协议解码") from None


def from_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != "api.ixunke.cn" or parsed.username
            or parsed.password or not parsed.path.startswith("/xizongcangqiong/api/")):
        raise ValueError("请求地址不是项目配置的上游接口")
    tokens = parse_qs(parsed.query).get("token") or []
    if len(tokens) != 1:
        raise ValueError("请求中没有唯一的登录 Token")
    return decode_request_token(tokens[0])


def load_material(text: str) -> str:
    text = text.strip().lstrip("\ufeff")
    if len(text) > 50_000_000:
        raise ValueError("登录材料文件过大")
    if text.startswith("https://"):
        return from_url(text)
    if text.startswith(("{", "[", '"')):
        try:
            data = json.loads(text)
        except ValueError:
            raise ValueError("登录材料不是有效 JSON") from None
        if isinstance(data, str):
            return load_material(data)
        if isinstance(data, dict):
            if isinstance(data.get("log"), dict) and isinstance(data["log"].get("entries"), list):
                for entry in reversed(data["log"]["entries"]):
                    request = entry.get("request") if isinstance(entry, dict) else None
                    url = request.get("url", "") if isinstance(request, dict) else ""
                    try:
                        return from_url(url)
                    except ValueError:
                        continue
                raise ValueError("HAR 中未找到该上游的已登录请求")
            token = data.get("token") or (data.get("data", {}).get("token") if isinstance(data.get("data"), dict) else None)
            if isinstance(token, str):
                return load_material(token)
        raise ValueError("未识别的登录材料结构")
    # A signed request value contains encrypted payload + timestamp; a base token
    # is used unchanged. Both are validated against upstream before installation.
    try:
        outer = base64.b64decode(text, validate=True).decode("utf-8")
    except (ValueError, UnicodeError):
        outer = ""
    if "#" in outer:
        return decode_request_token(text)
    return session_value(text)
