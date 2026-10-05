import os
import asyncio
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot


from langchain.agents import create_agent
from langchain_core.utils.uuid import uuid7
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


agent = create_agent(
    model = 'openai:gpt-6-luna',
    checkpointer = InMemorySaver()
)


bot = AsyncTeleBot(TELEGRAM_TOKEN)

@bot.message_handler(func = lambda message: True, content_types = ['text'])
async def ask(message):
    user_message = message.text
    config = {"configurable": {"thread_id": str(message.chat.id)}}
    text = ''
    draft_id = 1
    last_update = 0

    async for chunk in generate_response(user_message, config):
        text += chunk
        now = asyncio.get_running_loop().time()
        if now - last_update >= 0.5:
            await bot.send_message_draft(
                chat_id = message.chat.id,
                draft_id = draft_id,
                text = text
            )
            last_update = now

    await bot.send_message(message.chat.id, text)
    #TODO: Handle Telegram long message limit

async def generate_response(input: str, config):
    stream = agent.astream(
        {"messages": [{"role": "user", "content": input}]},
        config=config,
        stream_mode="messages"
    )

    async for message, metadata in stream:
        if message.content and isinstance(message.content, str):
            yield message.content

asyncio.run(bot.infinity_polling())