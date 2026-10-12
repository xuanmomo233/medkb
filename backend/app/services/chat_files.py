"""聊天附件解析：文本类 + docx（zipfile），原始 ≤4MB、正文 ≤8000 字。"""
import asyncio
import base64
import io
import re
import zipfile

TXT_EXT = frozenset("txt md csv tsv json log yaml yml xml ini conf py java sql htm html".split())
FILE_MAX_B64 = 5_500_000
FILE_MAX_RAW = 4 * 1024 * 1024
FILE_MAX_TXT = 8000
_DOCX_XML_MAX = 30 * 1024 * 1024

MSG_UNREADABLE = "这个文件读不了——支持 txt/md/docx 等文本类文件（≤4MB），PDF/扫描件请截图发我"
MSG_EMPTY = "文件里没有可读文字，扫描件/图片型 PDF 请截图发我"


def safe_name(name: str | None) -> str:
    return re.sub(r"[^\w.\-一-龥]", "_", str(name or "file"))[:60]


def _extract(name: str, b64: str) -> str | None:
    if len(b64) > FILE_MAX_B64:
        return None
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in TXT_EXT and ext != "docx":
        return None
    try:
        raw = base64.b64decode(re.sub(r"[^A-Za-z0-9+/=]", "", b64))
    except Exception:
        return None
    if len(raw) > FILE_MAX_RAW:
        return None
    try:
        if ext in TXT_EXT:
            return raw.decode("utf-8", errors="replace")[:FILE_MAX_TXT]
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            info = z.getinfo("word/document.xml")
            # 流式截断读取：不信任 zip 头里的 file_size（可伪造），防解压炸弹撑爆内存
            with z.open(info) as f:
                buf = f.read(_DOCX_XML_MAX + 1)
            if len(buf) > _DOCX_XML_MAX:
                return None
            xml = buf.decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", "", xml.replace("</w:p>", "\n"))[:FILE_MAX_TXT]
    except Exception:
        return None


async def file_text(name: str, b64: str) -> str | None:
    """返回正文；None=类型不支持/解析失败/超大"""
    return await asyncio.to_thread(_extract, name, b64)
