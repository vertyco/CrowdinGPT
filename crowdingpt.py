import asyncio
import json
import os
import re
import typing as t
from datetime import datetime
from pathlib import Path
from time import sleep

import openai
import requests
from aiocache import cached
from colorama import Fore, init
from crowdin_api import CrowdinClient
from dotenv import load_dotenv
from openai.error import APIConnectionError, RateLimitError, ServiceUnavailableError

from common.constants import PRICES, TRANSLATE
from common.models import Project, Source, Translation
from common.translate import TranslateManager

# Load .env file
load_dotenv()

# Crowdin API key, project ID, and OpenAI Key
CROWDIN_API_KEY = os.environ.get("CROWDIN_KEY")
openai.api_key = os.environ.get("OPENAI_KEY")
MODEL = os.environ.get("MODEL", "gpt-3.5-turbo")
AUTO = int(os.environ.get("AUTO", 0))
PRE_TRANSLATE = int(os.environ.get("PRE_TRANSLATE", 0))

# Endpoint override
if override := os.environ.get("ENDPOINT_OVERRIDE"):
    openai.api_base = override

# Headers for Crowdin API requests
HEADERS = {"Authorization": f"Bearer {CROWDIN_API_KEY}"}

# Init translator
translator = TranslateManager(deepl_key=os.environ.get("DEEPL_KEY"))

# Init colors
init()

# Init data paths
root_dir = Path(__file__).parent
system_prompt_path = root_dir / "prompt"
correction_prompt_dir = root_dir / "correction_prompts"
data_dir = root_dir / "data"
messages_dir = data_dir / "messages"
tokens_json = data_dir / "tokens.json"
processed_json = data_dir / "processed.json"

# Create folders if they dont exist
data_dir.mkdir(exist_ok=True)
messages_dir.mkdir(exist_ok=True)
# Create data files if they dont exist
if not tokens_json.exists():
    tokens_json.write_text(json.dumps({"total": 0, "prompt": 0, "completion": 0}))
if not processed_json.exists():
    processed_json.write_text("[]")

# Prepare correctional prompts
ACCENT_MISMATCH = (correction_prompt_dir / "accent_mismatch").read_text()
LENGTH_DIFFERENCE = (correction_prompt_dir / "length_difference").read_text()
PLACEHOLDER_MISMATCH = (correction_prompt_dir / "placeholder_mismatch").read_text()


def cyan(text: str):
    return Fore.CYAN + text + Fore.RESET


def yellow(text: str):
    return Fore.YELLOW + text + Fore.RESET


def green(text: str):
    return Fore.GREEN + text + Fore.RESET


def red(text: str):
    return Fore.RED + text + Fore.RESET


@cached(ttl=3600)
async def translate_chat(source_text: str, target_lang: str) -> str:
    system_prompt = system_prompt_path.read_text()
    messages = [
        {"role": "system", "content": system_prompt.strip().replace("{target_lang}", target_lang)},
        {
            "role": "system",
            "content": f"Translate the following text to {target_lang}",
        },
        {"role": "user", "content": source_text},
    ]

    if PRE_TRANSLATE:
        if translation := await translator.translate(source_text, target_lang):
            pre_translated = translation.text
            if pre_translated.strip() != source_text.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": "get_translation",
                            "arguments": json.dumps(
                                {"message": source_text, "to_language": target_lang}
                            ),
                        },
                    }
                )
                messages.append(
                    {
                        "role": "function",
                        "name": "get_translation",
                        "content": pre_translated,
                    }
                )

    functions_called = 0
    use_functions = True
    iterations = 0
    fails = 0
    corrections = []

    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0

    temperature = 0
    presence_penalty = 0
    frequency_penalty = 0

    while True:
        iterations += 1
        if iterations > 1 and temperature < 0.6:
            temperature += 0.1
            presence_penalty -= 0.1
            frequency_penalty -= 0.1

        if fails > 1:
            reply = ""
            break
        try:
            if functions_called > 7 or iterations > 10 or not use_functions:
                response = await openai.ChatCompletion.acreate(
                    model=MODEL,
                    messages=messages,
                    temperature=temperature,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                )
            else:
                response = await openai.ChatCompletion.acreate(
                    model=MODEL,
                    messages=messages,
                    temperature=temperature,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    functions=[TRANSLATE],
                )
        except ServiceUnavailableError as e:
            fails += 1
            print(red(f"ServiceUnavailableError, waiting 5 seconds before trying again: {e}"))
            sleep(5)
            print("Trying again...")
            continue
        except APIConnectionError as e:
            fails += 1
            print(red(f"APIConnectionError, waiting 5 seconds before trying again: {e}"))
            sleep(5)
            print("Trying again...")
            continue
        except RateLimitError as e:
            fails += 1
            print(red(f"Rate limted! Waiting 1 minute before retrying: {e}"))
            sleep(60)
            continue
        except Exception as e:
            fails += 1
            print(red(f"ERROR\n{json.dumps(messages, indent=2)}"))
            raise Exception(e)

        total_tokens += response["usage"].get("total_tokens", 0)
        prompt_tokens += response["usage"].get("prompt_tokens", 0)
        completion_tokens += response["usage"].get("completion_tokens", 0)

        message = response["choices"][0]["message"]
        reply: t.Optional[str] = message["content"]
        if reply:
            messages.append({"role": "assistant", "content": reply})
            source_placeholders = re.findall("{.*?}", source_text)
            reply_placeholders = re.findall("{.*?}", reply)
            if len(source_placeholders) != len(reply_placeholders):
                err = "Placeholder mismatch!"
                if err not in corrections:
                    print(err)
                    messages.append({"role": "system", "content": PLACEHOLDER_MISMATCH})
                    corrections.append(err)
                    continue
            if reply.count("`") != source_text.count("`"):
                err = "Accent count difference!"
                if err not in corrections:
                    print(err)
                    messages.append({"role": "system", "content": ACCENT_MISMATCH})
                    corrections.append(err)
                    continue
            if len(reply) - len(source_text) > 40:
                err = "Text length mismatch!"
                if err not in corrections:
                    print(err)
                    messages.append({"role": "system", "content": LENGTH_DIFFERENCE})
                    corrections.append(err)
                    continue

            break
        if function_call := message.get("function_call"):
            messages.append(message)
            func_name = function_call["name"]

            if func_name not in ("get_translation"):
                print(f"Invalid function called: {func_name}")
                messages.append(
                    {"role": "system", "content": f"{func_name} is not a valid function!"}
                )
                continue

            args = function_call.get("arguments", "{}")
            try:
                params = json.loads(args)
            except json.JSONDecodeError:
                print(f"Arguments failed to parse: {args}")
                messages.append(
                    {
                        "role": "function",
                        "content": "arguments failed to parse",
                        "name": "get_translation",
                    }
                )
                continue

            if "message" not in params or "to_language" not in params:
                print("Missing params for translate")
                messages.append(
                    {
                        "role": "function",
                        "content": f"{func_name} requires 'message' and 'to_language' arguments",
                        "name": func_name,
                    }
                )
                continue

            lang = translator.convert(params["to_language"])
            if not lang:
                print(f"Invalid target language! {params['to_language']}")
                messages.append(
                    {
                        "role": "function",
                        "content": "Invalid target language!",
                        "name": "get_translation",
                    }
                )
                continue

            try:
                translation = await translator.translate(params["message"], params["to_language"])
                if not translation:
                    messages.append(
                        {
                            "role": "function",
                            "content": "Translation failed!",
                            "name": "get_translation",
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": "function",
                            "content": translation.text,
                            "name": "get_translation",
                        }
                    )
            except Exception as e:
                print(f"Exception: {e}")
                messages.append(
                    {
                        "role": "function",
                        "content": f"Exception occured: {e}",
                        "name": "get_translation",
                    }
                )

            functions_called += 1

    file = messages_dir / f"dump_{round(datetime.now().timestamp())}.json"
    file.write_text(json.dumps(messages, indent=4))

    usage = json.loads(tokens_json.read_text())
    usage["total"] += total_tokens
    usage["prompt"] += prompt_tokens
    usage["completion"] += completion_tokens
    tokens_json.write_text(json.dumps(usage))

    # Static formatting
    if source_text.endswith(".") and not reply.endswith("."):
        reply += "."
    if source_text.endswith("\n") and not reply.endswith("\n"):
        reply += "\n"
    if source_text.startswith("\n") and not reply.startswith("\n"):
        reply = "\n" + reply
    if not source_text.endswith(".") and reply.endswith("."):
        reply = reply.rstrip(".")
    if source_text.startswith(" ") and not reply.startswith(" "):
        reply = " " + reply
    if source_text.endswith(" ") and not reply.endswith(" "):
        reply += " "

    if functions_called:
        print(f"Called translate function {functions_called} time(s)")

    return reply


async def get_source_strings(project_id: int, offset: int = 0):
    response = requests.get(
        f"https://api.crowdin.com/api/v2/projects/{project_id}/strings",
        headers=HEADERS,
        params={"offset": offset, "limit": 500},
    )
    return response.json()


async def upload_translation(project_id: int, string_id: int, language_id: int, text: str):
    data = {"stringId": string_id, "languageId": language_id, "text": text}
    response = requests.post(
        f"https://api.crowdin.com/api/v2/projects/{project_id}/translations",
        headers=HEADERS,
        json=data,
    )
    return response


# Check if string needs translation
async def needs_translation(project_id: int, string_id: int, language_id: str):
    params = {"stringId": string_id, "languageId": language_id}
    response = requests.get(
        f"https://api.crowdin.com/api/v2/projects/{project_id}/translations",
        headers=HEADERS,
        params=params,
    )
    translations = response.json()
    if not translations["data"]:
        return True
    if not translations["data"][0]["data"]:
        return True
    data = translations["data"][0]["data"]
    Translation.parse_obj(data)
    return False


async def main():
    if AUTO:
        print("Running in mostly-auto mode")
    else:
        print("Running in manual mode")
    processed = json.loads(processed_json.read_text())
    projects = CrowdinClient(token=CROWDIN_API_KEY).projects.with_fetch_all().list_projects()
    if not projects:
        print("NO PROJECTS!")
        return
    projects = projects["data"]
    for i in projects:
        project = Project.parse_obj(i["data"])
        print(f"Translating project: {project.name}")
        offset = 0
        sources = []
        while True:
            data = await get_source_strings(project.id, offset)
            if not data["data"]:
                break
            offset += 500
            sources += [entry["data"] for entry in data["data"]]
            print(f"Found {len(sources)} sources")

        for target_lang in project.targetLanguages:
            print(f"Doing translations for {target_lang.name}")
            for raw_source in sources:
                source = Source.parse_obj(raw_source)
                key = f"{project.id}{source.id}{target_lang.id}"
                if key in processed:
                    continue

                # Check if translation is needed
                if await needs_translation(project.id, source.id, target_lang.id):
                    print()
                    usage = json.loads(tokens_json.read_text())
                    prices = PRICES[MODEL]
                    input_cost = (usage["prompt"] / 1000) * prices[0]
                    output_cost = (usage["completion"] / 1000) * prices[1]
                    cost = round(input_cost + output_cost, 3)
                    print(f"Translating... (${cost} used overall)")
                    translation = await translate_chat(source.text, target_lang.name)
                    if not translation.strip():
                        print(
                            red(
                                f"Failed to translate to {target_lang.name}(Skipping): {source.text}"
                            )
                        )
                        continue
                    print("-" * 45 + "English" + "-" * 45)
                    print(f"{cyan(source.text)}\n")
                    print("-" * 45 + target_lang.name + "-" * 45)
                    print(f"{yellow(translation)}\n")
                    print("-" * 100)

                    txt = (
                        "Does this look okay?\n"
                        "- Leave blank and press ENTER to upload\n"
                        "- Type 'n' to skip\n"
                        "- Type 'c' to make correction and upload (Use CTRL + ENTER for new line)\n"
                        "Enter your response: "
                    )
                    confirm_conditions = [
                        source.text.count("{") != translation.count("{"),
                        source.text.count("`") != translation.count("`"),
                        abs(len(source.text) - len(translation)) > 500,
                        not AUTO,
                    ]
                    if any(confirm_conditions):
                        reply = input(red(txt))
                        if "n" in reply.lower():
                            print("Skipping...")
                            continue
                        if "c" in reply.lower():
                            translation = input(
                                cyan("Enter the correction. Type 'cancel' to skip\n")
                            )
                            if translation == "cancel":
                                print("Skipping...")
                                continue

                    upload_response = await upload_translation(
                        project.id, source.id, target_lang.id, translation
                    )
                    if upload_response.status_code == 201:
                        print(green("Translation uploaded successfully"))
                    else:
                        print(
                            red(
                                f"Error uploading translation:[{upload_response.status_code}] {upload_response.json()}"
                            )
                        )

                processed.append(key)
                processed_json.write_text(json.dumps(processed))


if __name__ == "__main__":
    asyncio.run(main())
