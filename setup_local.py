"""Optional command-line entry point for unattended local setup."""

import argparse
import asyncio
import sys

from captioning.runtime import Runtime
from captioning.service import data_directory


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["q3", "q4", "q5"], default="q4")
    parser.add_argument("--backend", choices=["cuda", "vulkan", "cpu"], default="cuda")
    args = parser.parse_args()
    runtime = Runtime(data_directory())
    runtime.install(args.profile, args.backend)
    try:
        while runtime.installing:
            print(runtime.state, flush=True)
            await asyncio.sleep(5)
        print(runtime.state, flush=True)
        if not runtime.ready(args.profile, args.backend):
            raise SystemExit(1)
    finally:
        runtime.cancel.set()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
