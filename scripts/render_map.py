#!/usr/bin/env python3
"""계획 문서의 Mermaid 구조도를 HTML로 감싸 Windows 브라우저로 띄운다.

WSL 환경 전제: explorer.exe로 Windows 기본 브라우저를 연다.
HTML은 Mermaid.js CDN을 사용하므로 인터넷 연결이 필요하다.
"""
import html as html_mod
import os
import re
import subprocess
import sys
import tempfile

MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def extract_mermaid(text):
    return [b.strip("\n") for b in MERMAID.findall(text)]


def build_html(blocks, title="구조도"):
    if blocks:
        divs = "\n".join(
            '<div class="mermaid">\n{}\n</div>'.format(html_mod.escape(b))
            for b in blocks
        )
    else:
        divs = "<p>이 문서에서 Mermaid 구조도를 찾지 못했습니다.</p>"
    return (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<title>{title}</title>\n"
        "<script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>\n"
        "<script>mermaid.initialize({{startOnLoad:true}});</script>\n"
        "<style>body{{font-family:sans-serif;padding:24px;}}</style>\n"
        "</head>\n<body>\n<h1>{title}</h1>\n{divs}\n</body>\n</html>\n"
    ).format(title=html_mod.escape(title), divs=divs)


def _to_windows_path(path):
    try:
        out = subprocess.run(
            ["wslpath", "-w", path], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return path


def open_in_browser(html_path):
    subprocess.run(["explorer.exe", _to_windows_path(html_path)], check=False)


def main(argv):
    if len(argv) < 2:
        print("사용법: render_map.py <계획문서.md>", file=sys.stderr)
        return 1
    src = argv[1]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    blocks = extract_mermaid(text)
    title = "구조도 — " + os.path.basename(src)
    html = build_html(blocks, title)
    fd, html_path = tempfile.mkstemp(suffix=".html", prefix="plan_guard_map_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    open_in_browser(html_path)
    print("열었습니다: {} (블록 {}개)".format(html_path, len(blocks)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
