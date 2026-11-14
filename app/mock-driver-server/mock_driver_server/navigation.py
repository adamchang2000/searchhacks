"""Navigation between the optimizer, simulation, and live search apps."""
from html import escape
from pathlib import Path

from django.http import HttpResponse

LINKS = (
    ("optimizer", "Optimizer", "https://searchhacks-optimizer.exe.xyz/optimizer"),
    ("simulation", "Simbed", "https://searchhacks-driver.exe.xyz/simulation"),
    ("chat", "Live queries", "https://searchhacks-driver.exe.xyz/chat"),
)


def render_driver_page(filename: str, active: str) -> HttpResponse:
    html = Path(__file__).with_name(filename).read_text()
    links = []
    for key, label, url in LINKS:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="{escape(url)}"{current}>{escape(label)}</a>')
    nav = '<nav class="project-nav" aria-label="Project navigation">' + "".join(links) + "</nav>"
    styles = """<style>
.project-nav{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.project-nav a{color:#7b8797;font-size:12px;text-decoration:none;white-space:nowrap}
.project-nav a:hover{text-decoration:underline}
.project-nav a[aria-current=page]{color:#263245;font-weight:600}
.chat-page header .controls{flex-wrap:wrap}
@media(max-width:800px){.project-nav{gap:10px}.project-nav a{font-size:11px}}
</style>"""
    html = html.replace("</head>", styles + "</head>", 1)
    html = html.replace("</h1>", "</h1>" + nav, 1)
    return HttpResponse(html)
