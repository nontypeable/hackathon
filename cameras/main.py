import asyncio
from config import  Config
from camera import Camera
from client import Client

async def main():
    for hash in Config.cameras.keys():
        await Camera(hash).connect()

    await Client.listen()

if __name__ == "__main__":
    asyncio.run(main())
