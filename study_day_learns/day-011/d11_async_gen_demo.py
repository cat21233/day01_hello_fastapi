import asyncio

async def llm_generator(text:str):
    for word in text.split( ):
        await asyncio.sleep(0.2)
        yield word
async def main():
    print("开始接收流式输出...")
    async for word in llm_generator("一只好,alien想你了"):
        print(f"收到: {word}")
    print("流式输出结束")
asyncio.run(main())