import asyncio
import json
import os
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
from pydantic import BaseModel

from constants import PRICES, TRANSLATE
from translate import TranslateManager

# Load .env file
load_dotenv()

# Crowdin API key, project ID, and OpenAI Key
CROWDIN_API_KEY = os.environ.get("CROWDIN_KEY")
openai.api_key = os.environ.get("OPENAI_KEY")
MODEL = os.environ.get("MODEL", "gpt-3.5-turbo")

# Endpoint override
if override := os.environ.get("ENDPOINT_OVERRIDE"):
    openai.api_base = override

# Headers for Crowdin API requests
HEADERS = {"Authorization": f"Bearer {CROWDIN_API_KEY}"}

# Init crowdin client
client = CrowdinClient(token=CROWDIN_API_KEY)

# Init translator
translator = TranslateManager()

# Init colors
init()

# Init processed json, messages dir and token count json
Path("messages").mkdir(exist_ok=True)
processed_json = Path("processed.json")
if not processed_json.exists():
    processed_json.write_text("[]")
tokens_json = Path("tokens.json")
if not tokens_json.exists():
    tokens_json.write_text(json.dumps({"total": 0, "prompt": 0, "completion": 0}))


system_prompt = """
You are an AI making doing translations for a Crowdin project, your goal is to translate text to {target_lang} while preserving Python string formatting accurately. Utilize function calls to increase accuracy.

Key considerations when translating:
- Only respond with the translated version of the source text.
- If needed, break strings up into smaller parts and call the translate function for each part to help with formatting.
- Do not translate anything wrapped in curly braces or '`'. These are placeholders/arguments and should be preserved.
- Retain the same amount of curly braces { and astrisks * in your translations.
- Do not introduce any new placeholders or additional spaces in the translation.
- Ensure the translated text retains the same style and formatting as the source text. This includes special characters (like '`' and '-') which must be kept in their original places.
- Handle lengthy texts by breaking them up into smaller, manageable parts for translation. This will make the task less cumbersome and more accurate.
- Maintain the same spacing as the source string. The beginning and ending of the translated string should mirror the source string.
- Avoid repetition in the translation. Each idea or concept should only be translated once.
- It is vital that the translated string is a close resemblance to the source string while making sense in the target language.

Use all available resources and your translation skills to provide the most accurate and contextually correct translations. Only respond with translated text.
"""
system_prompt_path = Path("prompt.txt")
if system_prompt_path.exists():
    system_prompt = system_prompt_path.read_text()
else:
    system_prompt_path.write_text(system_prompt)


class Source(BaseModel):
    id: int
    projectId: int
    fileId: int
    branchId: int
    directoryId: int
    identifier: str
    text: str
    type: str
    context: str
    maxLength: int
    isHidden: bool
    isDuplicate: bool
    masterStringId: t.Optional[str] = None
    revision: int
    hasPlurals: bool
    isIcu: bool
    labelIds: list
    createdAt: datetime
    updatedAt: t.Optional[datetime] = None


class Translation(BaseModel):
    id: int
    text: str
    pluralCategoryName: t.Optional[str] = None
    user: dict
    rating: int
    provider: t.Optional[str] = None
    isPreTranslated: bool
    createdAt: datetime


class Language(BaseModel):
    id: str
    name: str
    editorCode: str
    twoLettersCode: str
    threeLettersCode: str
    locale: str
    androidCode: str
    osxCode: str
    osxLocale: str
    pluralCategoryNames: t.List[str]
    pluralRules: str
    pluralExamples: t.List[str]
    textDirection: str
    dialectOf: t.Optional[str]


class Project(BaseModel):
    id: int
    userId: int
    sourceLanguageId: str
    targetLanguageIds: t.List[str]
    languageAccessPolicy: str
    name: str
    cname: t.Optional[str]
    identifier: str
    description: str
    visibility: str
    logo: t.Optional[str]
    publicDownloads: bool
    createdAt: datetime
    updatedAt: datetime
    lastActivity: datetime
    targetLanguages: t.List[Language]


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
    messages = [
        {"role": "system", "content": system_prompt.strip().replace("{target_lang}", target_lang)},
        {
            "role": "user",
            "content": f"Translate the following text to {target_lang}",
        },
        {"role": "user", "content": source_text},
    ]

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
    fails = 0
    corrections = []

    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    while True:
        if fails > 1:
            reply = ""
            break
        try:
            if functions_called > 6:
                response = await openai.ChatCompletion.acreate(
                    model=MODEL,
                    messages=messages,
                    temperature=0,
                    presence_penalty=-2,
                    frequency_penalty=-2,
                )
            else:
                response = await openai.ChatCompletion.acreate(
                    model=MODEL,
                    messages=messages,
                    temperature=0,
                    functions=[TRANSLATE],
                    presence_penalty=-2,
                    frequency_penalty=-2,
                )
        except ServiceUnavailableError as e:
            fails += 1
            print(f"ServiceUnavailableError, waiting 5 seconds before trying again: {e}")
            sleep(5)
            print("Trying again...")
            continue
        except APIConnectionError as e:
            fails += 1
            print(f"APIConnectionError, waiting 5 seconds before trying again: {e}")
            sleep(5)
            print("Trying again...")
            continue
        except RateLimitError as e:
            fails += 1
            print(f"Rate limted! Waiting 1 minute before retrying: {e}")
            sleep(60)
            continue
        except Exception as e:
            fails += 1
            print("ERROR\n", json.dumps(messages, indent=2))
            raise Exception(e)

        total_tokens += response["usage"].get("total_tokens", 0)
        prompt_tokens += response["usage"].get("prompt_tokens", 0)
        completion_tokens += response["usage"].get("completion_tokens", 0)

        message = response["choices"][0]["message"]
        reply: t.Optional[str] = message["content"]
        if reply:
            if "{" in reply and "{" not in source_text:
                err = "Placeholder mismatch!"
                if err not in corrections:
                    print(err)
                    messages.append(
                        {
                            "role": "system",
                            "content": "Source text doesn't have {} in it, but translation does. Correct this and reprint translation.",
                        }
                    )
                    corrections.append(err)
                    continue

            if reply.count("{") != source_text.count("{"):
                err = "Placeholder count difference!"
                if err not in corrections:
                    print(err)
                    messages.append(
                        {
                            "role": "user",
                            "content": "The source text and translation have a different amount of placeholder brackets, correct this and reprint the translation.",
                        }
                    )
                    corrections.append(err)
                    continue

            if abs(len(source_text) - len(reply)) > 40:
                err = "Text length mismatch!"
                if err not in corrections:
                    print(err)
                    messages.append(
                        {
                            "role": "user",
                            "content": "The difference in length between the source text and translation is greater than 40 characters, ensure this is correct and then reprint the translation.",
                        }
                    )
                    corrections.append(err)
                    continue

            break
        if function_call := message.get("function_call"):
            messages.append(message)
            func_name = function_call["name"]

            if func_name not in ["get_translation", "self_reflect"]:
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

    messages.append({"role": "assistant", "content": reply})
    filename = f"dump_{round(datetime.now().timestamp())}.json"
    Path(f"messages/{filename}").write_text(json.dumps(messages, indent=2))

    usage = json.loads(tokens_json.read_text())
    usage["total"] += total_tokens
    usage["prompt"] += prompt_tokens
    usage["completion"] += completion_tokens
    tokens_json.write_text(json.dumps(usage))

    # Static formatting
    if source_text.endswith("`") and not reply.endswith("`"):
        reply += "`"
    if source_text.startswith("`") and not reply.startswith("`"):
        reply = "`" + reply
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
    processed = json.loads(Path("processed.json").read_text())

    projects = client.projects.with_fetch_all().list_projects()
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
            # offset = data["pagination"]["offset"]
            # limit = data["pagination"]["limit"]
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

                    txt = "Does this look okay? Press ENTER to continue, or type 'n' to skip this translation for now\n"
                    confirm_conditions = [
                        source.text.count("{") != translation.count("{"),
                        # abs(len(source.text) - len(translation)) > 50,
                    ]
                    if any(confirm_conditions):
                        reply = input(red(txt))
                        if "n" in reply.lower():
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
                Path("processed.json").write_text(json.dumps(processed))


if __name__ == "__main__":
    asyncio.run(main())
