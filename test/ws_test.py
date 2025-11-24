import asyncio, websockets

async def run():
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        await ws.send('{"test":"ping"}')
        # optionally await a message:
        # msg = await ws.recv(); print("recv:", msg)

asyncio.run(run())