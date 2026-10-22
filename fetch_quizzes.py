import os
import json
from telethon import TelegramClient


API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = os.environ["TELEGRAM_SESSION"]

GROUP = "YOUR_GROUP_USERNAME"


client = TelegramClient(
    "quiz_session",
    API_ID,
    API_HASH
)


def load_json(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


async def main():

    await client.start(
        session=SESSION
    )

    quizzes = load_json(
        "quizzes.json"
    )

    metadata = load_json(
        "metadata.json"
    )


    messages = await client.get_messages(
        GROUP,
        limit=100
    )


    for message in messages:

        if not message.poll:
            continue


        poll = message.poll


        if poll.id in metadata["poll_ids"]:
            continue


        question = poll.question


        options = [
            answer.text
            for answer in poll.answers
        ]


        correct_index = 0

        if poll.quiz:

            correct_index = (
                poll.correct_answers[0]
                if poll.correct_answers
                else 0
            )


        explanation = (
            poll.explanation
            if poll.explanation
            else ""
        )


        quiz = [
            question,
            options,
            correct_index,
            explanation
        ]


        quizzes.append(quiz)


        metadata["poll_ids"].append(
            poll.id
        )


        print(
            "Saved:",
            question
        )


    save_json(
        "quizzes.json",
        quizzes
    )


    save_json(
        "metadata.json",
        metadata
    )


with client:
    client.loop.run_until_complete(
        main()
    )
