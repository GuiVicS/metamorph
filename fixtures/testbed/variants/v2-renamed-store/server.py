"""Server for v2-renamed-store variant."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from server import FixtureServer
import asyncio

async def main():
    base = Path(__file__).parent / 'public'
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = FixtureServer(base, port)
    await server.start()
    print(f"v2-renamed-store server running at http://localhost:{port}")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()

if __name__ == '__main__':
    asyncio.run(main())