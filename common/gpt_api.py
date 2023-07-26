import json
import os
import re
import typing as t
from datetime import datetime
from time import sleep

import openai
from aiocache import cached
from openai.error import (
    APIConnectionError,
    APIError,
    RateLimitError,
    ServiceUnavailableError,
)

from common.constants import TRANSLATE, red
from common.dirs import (
    correction_prompt_dir,
    messages_dir,
    system_prompt_path,
    tokens_json,
)
from common.translate_api import TranslateManager

LENGTH_DIFFERENCE = (correction_prompt_dir / "length_difference").read_text()
PLACEHOLDER_MISMATCH = (correction_prompt_dir / "placeholder_mismatch").read_text()


@cached(ttl=120)
async def call_openai(messages: t.List[dict], use_functions: bool):
    model = os.environ.get("MODEL", "gpt-3.5-turbo")
    kwargs = {
        "api_key": os.environ.get("OPENAI_KEY"),
        "api_base": os.environ.get("ENDPOINT_OVERRIDE"),
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "presence_penalty": -0.1,
        "frequency_penalty": -0.1,
    }
    if use_functions:
        kwargs["functions"] = [TRANSLATE]
    return await openai.ChatCompletion.acreate(**kwargs)


async def translate_string(
    translator: TranslateManager,
    source_text: str,
    target_lang: str,
) -> str:
    system_prompt_raw = system_prompt_path.read_text().strip()
    system_prompt = system_prompt_raw.replace("{target_language}", target_lang)
    model = os.environ.get("MODEL", "gpt-3.5-turbo")

    source_text = source_text.replace("`", "<x>")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": source_text, "name": "source_text"},
    ]

    if int(os.environ.get("PRE_TRANSLATE", 0)):
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
                                {
                                    "message": source_text,
                                    "to_language": target_lang,
                                }
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

    while True:
        iterations += 1

        if fails > 1:
            reply = ""
            break

        try:
            use_functions = (
                False
                if (
                    functions_called > 7
                    or iterations > 10
                    or not use_functions
                    or model.endswith("0301")
                )
                else True
            )
            response = await call_openai(messages, use_functions)
        except ServiceUnavailableError as e:
            fails += 1
            print(red(f"ServiceUnavailableError, waiting 5 seconds before trying again: {e}"))
            sleep(5)
            print("Trying again...")
            continue
        except (APIConnectionError, APIError) as e:
            fails += 1
            print(red(f"APIConnectionError/APIError, waiting 5 seconds before trying again: {e}"))
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
                    messages.append({"role": "user", "content": PLACEHOLDER_MISMATCH})
                    corrections.append(err)
                    continue
            if len(reply) - len(source_text) > 40:
                err = "Text length mismatch!"
                if err not in corrections:
                    print(err)
                    messages.append({"role": "user", "content": LENGTH_DIFFERENCE})
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

    files = sorted(messages_dir.iterdir(), key=lambda f: f.stat().st_mtime)
    for f in files[:-9]:
        f.unlink(missing_ok=True)

    file = messages_dir / f"dump_{round(datetime.now().timestamp())}.json"
    file.write_text(json.dumps(messages, indent=4))

    usage = json.loads(tokens_json.read_text())
    usage["total"] += total_tokens
    usage["prompt"] += prompt_tokens
    usage["completion"] += completion_tokens
    tokens_json.write_text(json.dumps(usage))

    reply = reply.replace("<x>", "`")

    # Static formatting
    if source_text.endswith(".") and not reply.endswith("."):
        reply += "."
    if source_text.endswith("\n") and not reply.endswith("\n"):
        reply += "\n"
    if source_text.startswith("\n") and not reply.startswith("\n"):
        reply = "\n" + reply
    if not source_text.endswith(".") and reply.endswith("."):
        reply = reply.rstrip(".")
    if source_text.startswith("{}\n") and not reply.startswith("{}\n"):
        reply = "{}\n" + reply
    if source_text.startswith(" ") and not reply.startswith(" "):
        reply = " " + reply
    if source_text.endswith(" ") and not reply.endswith(" "):
        reply += " "

    if functions_called:
        print(f"Called translate function {functions_called} time(s)")

    return reply
