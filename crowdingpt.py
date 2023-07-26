import asyncio
import json
import os

from dotenv import load_dotenv

from common.constants import PRICES, cyan, green, red, yellow
from common.crowdin_api import CrowdinAPI
from common.dirs import processed_json, tokens_json
from common.gpt_api import translate_string
from common.translate_api import TranslateManager

# Load .env file
load_dotenv()

MODEL = os.environ.get("MODEL", "gpt-3.5-turbo")
AUTO = int(os.environ.get("AUTO", 0))
PROCESS_QA = True


async def process_translations():
    if AUTO == 1:
        print("Running in mostly-auto mode")
    elif AUTO == 2:
        print("Running in full-auto mode")
    else:
        print("Running in manual mode")
    processed = json.loads(processed_json.read_text())
    client = CrowdinAPI(api_key=os.environ.get("CROWDIN_KEY"))
    translator = TranslateManager(deepl_key=os.environ.get("DEEPL_KEY"))

    projects = await client.get_projects()
    if not projects:
        print("NO PROJECTS!")
        return
    for project in projects:
        print(f"Translating project: {project.name}")
        strings = await client.get_strings(project.id)

        # if PROCESS_QA:
        #     # Map out strings
        #     mapped = {string.id: string for string in strings}
        #     issues = await client.get_qa_issues(project.id)
        #     for issue in issues:
        #         target_source = mapped.get(issue.stringId)
        #         if not target_source:
        #             continue

        print(f"Found {len(strings)} sources")
        for target_lang in project.targetLanguages:
            print(green(f"Doing translations for {target_lang.name}"))
            for source_string in strings:
                key = f"{project.id}{source_string.id}{target_lang.id}"
                if key in processed:
                    continue
                if await client.needs_translation(project.id, source_string.id, target_lang.id):
                    print()
                    usage = json.loads(tokens_json.read_text())
                    input_price, output_price = PRICES[MODEL]
                    input_cost = (usage["prompt"] / 1000) * input_price
                    output_cost = (usage["completion"] / 1000) * output_price
                    cost = round(input_cost + output_cost, 3)
                    print(f"Translating... (${cost} used overall)")
                    translation = await translate_string(
                        translator, source_string.text, target_lang.name
                    )
                    if not translation.strip():
                        print(
                            red(
                                f"Failed to translate to {target_lang.name}(Skipping): {source_string.text}"
                            )
                        )
                        continue
                    print("-" * 45 + "English" + "-" * 45)
                    print(f"{cyan(source_string.text)}\n")
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
                    review = False
                    if source_string.text.count("{") != translation.count("{"):
                        print("bracket mismatch")
                        review = True
                    if source_string.text.count("`") != translation.count("`"):
                        print("backtick mismatch")
                        review = True
                    if not AUTO:
                        review = True
                    if review:
                        if AUTO == 2:
                            print(red("Auto skipping..."))
                            continue
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

                    await client.upload_translation(
                        project.id,
                        source_string.id,
                        target_lang.id,
                        translation,
                    )

                processed.append(key)
                processed_json.write_text(json.dumps(processed))


if __name__ == "__main__":
    asyncio.run(process_translations())
