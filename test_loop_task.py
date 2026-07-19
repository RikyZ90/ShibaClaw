import asyncio
from asyncio import Task

def _test_task(t: Task | None):
    if t is not None:
        # In Python 3.11+, Task has the cancelling() method
        # but mypy might not know about it if types-asyncio isn't updated
        pass
