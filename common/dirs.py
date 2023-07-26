import json
from pathlib import Path

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

# Create folders if they dont exist
data_dir.mkdir(exist_ok=True)
messages_dir.mkdir(exist_ok=True)
revisions_dir.mkdir(exist_ok=True)
# Create data files if they dont exist
if not tokens_json.exists():
    tokens_json.write_text(json.dumps({"total": 0, "prompt": 0, "completion": 0}))
if not processed_json.exists():
    processed_json.write_text("[]")
