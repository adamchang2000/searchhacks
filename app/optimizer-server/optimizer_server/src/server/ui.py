"""Serves the built dashboard (app/optimizer-ui/dist) from the optimizer server, so the
dashboard and the API share one origin and one port. Every non-/api path that isn't a
built file gets index.html, so client-side routes (e.g. /searches) work on reload."""

import os
from pathlib import Path

from django.http import HttpResponse, HttpResponseNotFound
from django.views.static import serve

# app/optimizer-server/optimizer_server/src/server/ui.py -> repo root is six levels up.
_REPO_ROOT = Path(__file__).resolve().parents[5]
UI_DIST_DIR = Path(os.environ.get("UI_DIST_DIR", _REPO_ROOT / "app" / "optimizer-ui" / "dist"))

NOT_BUILT = (
    "Dashboard not built. Run `npm run build -w @searchhacks/optimizer-ui` "
    f"(expected files in {UI_DIST_DIR})."
)


def ui(request, path: str = ""):
    if path.startswith("api/") or path == "api":
        return HttpResponseNotFound()
    index = UI_DIST_DIR / "index.html"
    if not index.is_file():
        return HttpResponse(NOT_BUILT, status=503, content_type="text/plain")

    target = (UI_DIST_DIR / path).resolve()
    if path and target.is_relative_to(UI_DIST_DIR.resolve()) and target.is_file():
        # Built assets have hashed names, so they can be cached forever.
        response = serve(request, path, document_root=UI_DIST_DIR)
        if path.startswith("assets/"):
            response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    response = serve(request, "index.html", document_root=UI_DIST_DIR)
    response["Cache-Control"] = "no-cache"
    return response
