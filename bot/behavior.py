import json
from typing import Union, Any

import requests

from .config import get_config
from .memory import BotMemory


class Bot:

    auto_forgets_after_minutes: int = 30

    numeric_questions_suffix = {"ar": "(أدخل رقما)", "fr": "(Répondez avec un numéro)"}

    def __init__(self, memory_store: Any, chatting_to: str):
        self.chatting_to = chatting_to
        self.memory = BotMemory(memory_store, self.auto_forgets_after_minutes)
        self.config = get_config()
        self.answers_payload = {}

    async def chat(self, the_bla_bla):

        if self._is_just_getting_started(the_bla_bla):
            print("Getting Started")
            await self._start_anew()
        else:
            if the_bla_bla.get("message"):
                # make sure this is something worth processing
                if not self.worth_processing(the_bla_bla):
                    print("Meh, not worth processing...")
                    return  # return early here.

                reply = self.get_reply_from_bla_bla(the_bla_bla)
                await self.process_reply(reply)

    def worth_processing(self, the_bla_bla) -> bool:
        # Nothing to process if the message is just an Echo or is not there.
        return the_bla_bla.get("message") or not the_bla_bla.get("is_echo")

    async def _start_anew(self):
        await self.forget()
        await self.init_answers_payload()
        self._send_button_question(
            question="Choisissez votre langue - اختر لغتك",
            choices=[("العربية", "ar"), ("Français", "fr")],
        )

    async def process_reply(self, reply: str):
        print("Reply is:", reply)
        answers = await self._get_memorized_answers()
        if not answers:
            await self._start_anew()
            return

        self.answers_payload = answers
        server_questions = await self.server_questions
        at_question = self.answers_payload.get("at_question")
        if at_question == -1:

            if reply not in ["ar", "fr"]:
                await self._start_anew()
                return

            self.answers_payload["lang"] = reply
            self.answers_payload["answers"] = {}

        if not self.answers_payload.get("lang"):
            await self._start_anew()
            return

        lang = self.answers_payload["lang"]
        question = server_questions[at_question]
        question_id = question["id"]
        self.answers_payload["answers"][question_id] = reply

        # next question
        at_question += 1

        if at_question >= len(server_questions):  # finished
            severity = self.send_answers_to_server(self.answers_payload["answers"])
            return

        next_question = server_questions[at_question]
        while self.can_skip_next_question(next_question):
            at_question += 1
            try:
                next_question = server_questions[at_question]
            except KeyError:
                severity = self.send_answers_to_server(self.answers_payload["answers"])
                return

        next_question_type = next_question["format"]["type"]
        next_question_text = next_question[f"text_{lang}"]

        if next_question_type in ["radio"]:
            self._send_button_question(
                next_question_text,
                [
                    (choice[f"label_{lang}"], choice["value"])
                    for choice in next_question["format"]["choices"]
                ],
            )
        else:
            if next_question_type in ["number", "select"]:
                next_question_text = (
                    f"{next_question_text} {self.numeric_questions_suffix[lang]}"
                )
            self._send_text_question(next_question_text)

        self.answers_payload["at_question"] = at_question
        await self._update_memory()

    def is_valid_reply(self, question, reply) -> bool:
        pass

    def get_reply_from_bla_bla(self, the_bla_bla) -> str:
        # `quick_reply`: the user responded to one of the quick reply questions
        # `text`: the user responded to a plain text question (Age) or sent a random string
        message = the_bla_bla.get("message")
        if message.get("quick_reply"):
            return message.get("quick_reply").get("payload")
        return message.get("text")

    @property
    async def server_questions(self) -> dict:
        if not hasattr(self, "_questions"):
            # Does the bot have the question already off the top of his head?
            questions = await self._get_questions_from_memory()
            if not questions:  # nope
                res = requests.get(self.config.questions_url)
                questions = res.json()
                # make the bot memorize the questions for a bit to reduce load on the server.
                # the reason we want to memorize it for a short time only and not forever is
                # the questions could get updated or reordered in the server.
                await self._remember_questions(questions)
            # cache it internally to the class so calling the property won't hit Redis nor the Server
            self._questions = questions
        return self._questions

    def can_skip_next_question(self, next_question):
        depends_on_question = next_question.get("depends_on_question")
        if not depends_on_question:
            return False

        dependant_value = self.answers_payload["answers"][depends_on_question]
        return dependant_value == next_question.get("depends_on_question_value")

    def get_server_question_by_id(self, id: int) -> str:
        for question in self.server_questions:
            if question.get("id") == id:
                return question

    def send_answers_to_server(self, answers: dict) -> dict:

        payload = {"facebook_sender_id": self.chatting_to}
        for question_id, answer_value in answers.items():
            key = self.get_server_question_by_id(question_id)
            payload[key] = answer_value

        res = requests.post(self.config.questions_url, json=payload)

        severity = res.json()["severity"]
        self._send_text_question(f"You are at severity {severity}")
        self.answers_payload = {}
        await self.forget()
        return severity

    async def _get_memorized_answers(self) -> Union[dict, str]:
        return await self.memory.get(self.chatting_to)

    async def _update_memory(self):
        await self.memory.set(self.chatting_to, self.answers_payload)

    async def _get_questions_from_memory(self) -> dict:
        return await self.memory.get("questions")

    async def _remember_questions(self, questions: dict):
        await self.memory.set("questions", questions)

    async def forget(self):
        await self.memory.delete_all(self.chatting_to)

    def _is_just_getting_started(self, the_bla_bla) -> bool:
        return the_bla_bla.get("postback", {}).get("payload") == "start"

    def _send_button_question(self, question: str, choices):
        quick_replies = [
            {"content_type": "text", "title": choice_value, "payload": choice_key,}
            for choice_value, choice_key in choices
        ]
        self._send_chat_message(
            {"text": question, "quick_replies": quick_replies,}
        )

    def _send_text_question(self, question_text: str):
        self._send_chat_message({"text": question_text})

    def _send_chat_message(self, message_payload: dict):
        self._send_typing_indicator("on")
        print(f"sending message to {self.chatting_to}")
        params = {"access_token": self.config.facebook_page_access_token}
        headers = {"Content-Type": "application/json"}

        data = json.dumps(
            {
                "recipient": {"id": self.chatting_to},
                "messaging_type": "RESPONSE",
                "message": message_payload,
            }
        )
        r = requests.post(
            self.config.facebook_graph_url, params=params, headers=headers, data=data,
        )
        print(r.status_code)
        print(r.text)
        self._send_typing_indicator("off")

    def _send_typing_indicator(self, switch="on"):
        params = {"access_token": self.config.facebook_page_access_token}

        data = {
            "recipient": {"id": self.chatting_to},
            "sender_action": f"typing_{switch}",
        }
        r = requests.post(self.config.facebook_graph_url, params=params, json=data,)

    async def init_answers_payload(self):
        self.answers_payload = {"at_question": -1, "answers": {}}
        await self._update_memory()
