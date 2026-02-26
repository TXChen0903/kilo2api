import asyncio
from core import run
from provider import KiloProvider

if __name__ == "__main__":
    asyncio.run(run(KiloProvider()))
