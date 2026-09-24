"""Network and storage capture dimensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from playwright.async_api import Page, Request, Response
import json


@dataclass
class NetworkCapture:
    requests: list[dict] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    websockets: list[dict] = field(default_factory=list)
    sse: list[dict] = field(default_factory=list)

    def to_catalogue(self) -> dict:
        """Convert to NetworkCatalogue format."""
        # Deduplicate by URL pattern
        patterns = {}
        for req in self.requests:
            pattern = self._url_to_pattern(req["url"])
            if pattern not in patterns:
                patterns[pattern] = {
                    "method": req["method"],
                    "url_pattern": pattern,
                    "request_shape": req.get("post_data_shape", {}),
                    "response_shape": {},
                    "headers": {k: v for k, v in req.get("headers", {}).items() if k.lower() not in ["cookie", "authorization"]},
                    "is_graphql": req.get("is_graphql", False),
                    "graphql_op_name": req.get("graphql_op_name"),
                    "graphql_doc_hash": req.get("graphql_doc_hash"),
                }
            # Merge response shape
            for resp in self.responses:
                if resp["request_id"] == req["request_id"]:
                    patterns[pattern]["response_shape"] = resp.get("body_shape", {})
                    break

        return {
            "requests": list(patterns.values()),
            "websocket_endpoints": self.websockets,
            "sse_endpoints": self.sse,
        }

    @staticmethod
    def _url_to_pattern(url: str) -> str:
        """Convert URL to pattern (replace IDs with placeholders)."""
        import re
        # Replace UUIDs
        url = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/:uuid", url)
        # Replace long numeric IDs
        url = re.sub(r"/\d{6,}(?=/|$)", "/:id", url)
        # Replace long alphanumeric
        url = re.sub(r"/[A-Za-z0-9_-]{20,}(?=/|$)", "/:id", url)
        return url


class NetworkMonitor:
    """Monitors network activity during crawl."""

    def __init__(self) -> None:
        self.capture = NetworkCapture()
        self._request_map: dict[str, dict] = {}

    def attach(self, page: Page) -> None:
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("websocket", self._on_websocket)

    def _on_request(self, request: Request) -> None:
        req_id = request.headers.get("x-request-id", id(request))
        post_data = request.post_data or ""
        post_shape = self._shape_of(post_data)

        # Detect GraphQL
        is_graphql = False
        op_name = None
        doc_hash = None
        if post_data:
            try:
                data = json.loads(post_data)
                if isinstance(data, dict) and ("query" in data or "operationName" in data):
                    is_graphql = True
                    op_name = data.get("operationName")
                    # Simple hash of query
                    import hashlib
                    doc_hash = hashlib.sha256(data.get("query", "").encode()).hexdigest()[:16]
            except json.JSONDecodeError:
                pass

        req_info = {
            "request_id": req_id,
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": post_data,
            "post_data_shape": post_shape,
            "resource_type": request.resource_type,
            "is_graphql": is_graphql,
            "graphql_op_name": op_name,
            "graphql_doc_hash": doc_hash,
        }
        self._request_map[req_id] = req_info
        self.capture.requests.append(req_info)

    def _on_response(self, response: Response) -> None:
        req_id = response.request.headers.get("x-request-id", id(response.request))
        body_shape = {}

        # Try to get body shape
        # Note: We can't easily get response body in Playwright without extra setup
        # For now, we'll note the content type and status
        content_type = response.headers.get("content-type", "")
        body_shape = {"content_type": content_type, "status": response.status}

        resp_info = {
            "request_id": req_id,
            "url": response.url,
            "status": response.status,
            "headers": dict(response.headers),
            "body_shape": body_shape,
        }
        self.capture.responses.append(resp_info)

    def _on_websocket(self, ws) -> None:
        ws_info = {
            "url": ws.url,
            "headers": {},
            "messages_sample": [],
        }
        self.capture.websockets.append(ws_info)

        # Try to capture a few messages
        def on_frame(frame):
            if len(ws_info["messages_sample"]) < 5:
                try:
                    if isinstance(frame, str):
                        ws_info["messages_sample"].append({"type": "text", "data": frame[:500]})
                    else:
                        ws_info["messages_sample"].append({"type": "binary", "size": len(frame)})
                except Exception:
                    pass

        ws.on("framereceived", on_frame)

    def _shape_of(self, data: str) -> dict:
        """Infer shape from JSON string."""
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            return self._infer_shape(parsed)
        except json.JSONDecodeError:
            return {"type": "string", "length": len(data)}

    def _infer_shape(self, obj: Any, max_depth: int = 3) -> dict:
        if max_depth <= 0:
            return {"type": "..."}
        if obj is None:
            return {"type": "null"}
        if isinstance(obj, bool):
            return {"type": "boolean"}
        if isinstance(obj, (int, float)):
            return {"type": "number"}
        if isinstance(obj, str):
            return {"type": "string", "length": len(obj)}
        if isinstance(obj, list):
            if not obj:
                return {"type": "array", "items": "empty"}
            # Sample first few items
            items = [self._infer_shape(item, max_depth - 1) for item in obj[:3]]
            return {"type": "array", "items": items}
        if isinstance(obj, dict):
            return {
                "type": "object",
                "properties": {k: self._infer_shape(v, max_depth - 1) for k, v in list(obj.items())[:10]},
            }
        return {"type": type(obj).__name__}


class StorageCapture:
    """Captures storage inventory."""

    @staticmethod
    async def capture(page: Page) -> dict:
        script = """
        () => {
            const result = {
                localStorage: {},
                sessionStorage: {},
                indexedDB: [],
                cookies: [],
            };

            // localStorage
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const val = localStorage.getItem(key);
                result.localStorage[key] = {type: typeof val, length: val?.length || 0};
            }

            // sessionStorage
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const val = sessionStorage.getItem(key);
                result.sessionStorage[key] = {type: typeof val, length: val?.length || 0};
            }

            // IndexedDB
            if (window.indexedDB) {
                try {
                    const dbs = await indexedDB.databases();
                    for (const db of dbs) {
                        result.indexedDB.push({
                            name: db.name,
                            version: db.version,
                            objectStores: [],
                        });
                    }
                } catch (e) {
                    // Cross-origin or permission issue
                }
            }

            // Cookie names only
            result.cookies = document.cookie.split(';').map(c => c.trim().split('=')[0]).filter(Boolean);

            return result;
        }
        """
        return await page.evaluate(script)