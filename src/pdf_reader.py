"""
PDF deep reader: download arxiv PDF, extract text, generate deep review via Claude.
"""

import os
import tempfile
from pathlib import Path

import aiohttp
import anthropic
from PyPDF2 import PdfReader


async def deep_review(arxiv_id: str, interests_summary: str = "") -> str:
    """
    Given an arxiv_id, download the PDF, extract text from the first 10 pages,
    and generate a deep review in Chinese using Claude Haiku.

    Args:
        arxiv_id: e.g. "2401.12345"
        interests_summary: brief description of user's research interests for context

    Returns:
        Review text (Chinese) or empty string on failure.
    """
    pdf_path = None
    try:
        # 1. Download PDF to temp file
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_path = Path(tempfile.mkdtemp()) / f"{arxiv_id.replace('/', '_')}.pdf"

        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    print(f"  PDF download failed for {arxiv_id}: HTTP {resp.status}")
                    return ""
                pdf_bytes = await resp.read()
                pdf_path.write_bytes(pdf_bytes)

        # 2. Extract text from first 10 pages
        reader = PdfReader(str(pdf_path))
        pages_to_read = min(10, len(reader.pages))
        text_parts = []
        for i in range(pages_to_read):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n".join(text_parts)
        if not full_text.strip():
            print(f"  No text extracted from PDF {arxiv_id}")
            return ""

        # Truncate to ~15k chars to stay within token limits
        full_text = full_text[:15000]

        # 3. Generate deep review via Claude Haiku
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        context_line = ""
        if interests_summary:
            context_line = f"\n用户的研究方向：{interests_summary}\n"

        prompt = f"""请根据以下论文内容，用中文撰写一份深度review。{context_line}

要求输出以下四个部分：

1. **核心方法与贡献**（2-3句话概括论文最重要的方法和贡献）
2. **技术细节**（关键公式、算法或架构的简要描述，帮助读者快速理解技术方案）
3. **优点与局限**（各列出2-3点）
4. **与用户研究方向的潜在联系和启发**（如何借鉴、可以探索的方向）

论文内容：
{full_text}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        review_text = response.content[0].text
        return review_text.strip()

    except Exception as e:
        print(f"  Deep review failed for {arxiv_id}: {e}")
        return ""

    finally:
        # 4. Clean up temp PDF
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
                pdf_path.parent.rmdir()
            except OSError:
                pass
