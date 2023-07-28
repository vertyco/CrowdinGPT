import asyncio

from common import PROCESS_QA
from common.constants import yellow
from common.processing import process_translations


async def main():
    if PROCESS_QA:
        print(yellow("QA MODE"))
    else:
        print(yellow("TRANSLATE MODE"))
    await process_translations()


if __name__ == "__main__":
    asyncio.run(main())
