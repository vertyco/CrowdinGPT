import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ENV variables
OPENAI_KEY = os.environ.get("OPENAI_KEY")
MODEL = os.environ.get("MODEL", "gpt-3.5-turbo")
ENDPOINT_OVERRIDE = os.environ.get("ENDPOINT_OVERRIDE")
AUTO = int(os.environ.get("AUTO", 0))
PRE_TRANSLATE = int(os.environ.get("PRE_TRANSLATE", 0))
PROCESS_QA = int(os.environ.get("PROCESS_QA", 0))
DEEPL_KEY = os.environ.get("DEEPL_KEY")
CROWDIN_KEY = os.environ.get("CROWDIN_KEY")

# Init data paths
root_dir = Path(__file__).parent.parent
system_prompt_path = root_dir / "system_prompt"
correction_prompt_dir = root_dir / "correction_prompts"
qa_prompt_dir = root_dir / "qa_prompts"

data_dir = root_dir / "data"
messages_dir = data_dir / "messages"
revisions_dir = data_dir / "revisions"
tokens_json = data_dir / "tokens.json"
processed_json = data_dir / "processed.json"
processed_qa_json = data_dir / "processed_qa.json"

# Create folders if they dont exist
data_dir.mkdir(exist_ok=True)
messages_dir.mkdir(exist_ok=True)
revisions_dir.mkdir(exist_ok=True)
# Create data files if they dont exist
if not tokens_json.exists():
    tokens_json.write_text(json.dumps({"total": 0, "prompt": 0, "completion": 0}))
if not processed_json.exists():
    processed_json.write_text("[]")
if not processed_qa_json.exists():
    processed_qa_json.write_text("[]")


LENGTH_DIFFERENCE = (correction_prompt_dir / "length_difference").read_text()
PLACEHOLDER_MISMATCH = (correction_prompt_dir / "placeholder_mismatch").read_text()
BACKTICK_MISMATCH = (correction_prompt_dir / "backtick_mismatch").read_text()
