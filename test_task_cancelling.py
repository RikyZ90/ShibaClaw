import typing
from asyncio import Task

def check_task(t: Task | None):
    if t is not None:
        print(t.cancelling())

import asyncio
async def main():
    check_task(asyncio.current_task())

asyncio.run(main())
