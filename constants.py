TRANSLATE = {
    "name": "get_translation",
    "description": "Translate text to another language",
    "parameters": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "the text to translate"},
            "to_language": {
                "type": "string",
                "description": "the target language to translate to",
            },
        },
        "required": ["message", "to_language"],
    },
}
REFLECT = {
    "name": "ask_question",
    "description": "Ask ChatGPT a question",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
        },
        "required": ["question"],
    },
}
PRICES = {
    "gpt-3.5-turbo": [0.0015, 0.002],
    "gpt-3.5-turbo-16k": [0.003, 0.004],
    "gpt-4": [0.03, 0.06],
}
