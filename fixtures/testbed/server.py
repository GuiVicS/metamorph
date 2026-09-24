"""Simple HTTP server for the fixture testbed."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from aiohttp import web


class FixtureServer:
    """Serves the testbed fixture and its variants."""

    def __init__(self, base_path: Path, port: int = 8765) -> None:
        self.base_path = base_path
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self.runner: web.AppRunner | None = None

    def _setup_routes(self) -> None:
        self.app.router.add_get('/{tail:.*}', self.handle_request)

    async def handle_request(self, request: web.Request) -> web.Response:
        tail = request.match_info['tail']
        if not tail:
            tail = 'index.html'

        # Security: prevent path traversal
        try:
            file_path = (self.base_path / tail).resolve()
            if not file_path.is_relative_to(self.base_path.resolve()):
                return web.Response(status=403, text="Forbidden")
        except Exception:
            return web.Response(status=404, text="Not Found")

        if not file_path.exists():
            # Try index.html for SPA routing
            file_path = (self.base_path / 'index.html').resolve()

        if file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()
            return web.Response(body=content, content_type=mime_type or 'application/octet-stream')

        return web.Response(status=404, text="Not Found")

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, 'localhost', self.port)
        await site.start()
        print(f"Fixture server running at http://localhost:{self.port}")

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()


async def main() -> None:
    import sys
    base = Path(__file__).parent / 'public'
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = FixtureServer(base, port)
    await server.start()
    try:
        await asyncio.Event().wait()  # Run forever
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()


if __name__ == '__main__':
    asyncio.run(main())