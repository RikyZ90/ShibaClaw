import asyncio
import os
import sys

from shibaclaw.agent.tools.shell import ExecTool

async def main():
    tool = ExecTool()
    # Test multiple commands with &&
    res1 = await tool.execute("echo 1 && echo 2")
    print("Test &&:", res1)
    
    # Test multiple commands with ;
    res2 = await tool.execute("echo 1 ; echo 2")
    print("Test ;:", res2)

    # Test newline separated commands
    res3 = await tool.execute("echo 1\necho 2")
    print("Test newline:", res3)

if __name__ == "__main__":
    asyncio.run(main())
