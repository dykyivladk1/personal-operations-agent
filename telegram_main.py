import os
import asyncio
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot
from openai import OpenAI

from langchain.agents import create_agent
from langchain.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent.tools import (
    create_event,
    get_events,
    create_email_draft,
    get_emails,
    send_email
)


load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
client = OpenAI()

agent = create_agent(
    model = 'openai:gpt-6-luna',
    checkpointer = InMemorySaver(),
    tools = [
        get_events,
        create_event,
        get_emails,
        create_email_draft,
        send_email
    ]
)


bot = AsyncTeleBot(TELEGRAM_TOKEN)

@bot.message_handler(func = lambda message: True, content_types = ['text'])
async def ask(message, user_message = None):

    if user_message is None:
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
        {
            "messages": [
                {
                    "role": "user",
                    "content": input,
                }
            ]
        },
        config=config,
        stream_mode="messages",
    )

    async for message, metadata in stream:
        if isinstance(message, AIMessage):
            chunk = str(message.text)

            if chunk:
                yield chunk


@bot.message_handler(content_types = ['voice'])
async def handle_voice(message):
    file_info = await bot.get_file(message.voice.file_id)
    audio_bytes = await bot.download_file(file_info.file_path)

    with open('voice.ogg', 'wb') as file:
        file.write(audio_bytes)

    with open('voice.ogg', 'rb') as audio_file:
        transcription = client.audio.transcriptions.create(
            model = 'gpt-transcribe', file = audio_file
        )

    await ask(message = message,
              user_message = transcription.text)


asyncio.run(bot.infinity_polling())