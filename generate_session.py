"""Run LOCALLY (needs interactive phone/code input) to create TELEGRAM_SESSION.

    export TELEGRAM_API_ID=...  TELEGRAM_API_HASH=...
    python generate_session.py

Store the printed string as a GitHub secret. Never commit or share it.
"""
import os

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

with TelegramClient(
    StringSession(), int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"]
) as client:
    print("\nSESSION STRING (keep secret):\n")
    print(client.session.save())
