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
            "formatlity": {
                "type": "string",
                "enum": ["less", "more", "prefer_more", "prefer_less"],
                "description": "controls whether translations should lean toward informal (less) or formal language (more)",
            },
        },
        "required": ["message", "to_language"],
    },
}
PRICES = {
    "gpt-3.5-turbo": [0.0015, 0.002],
    "gpt-3.5-turbo-0301": [0.0015, 0.002],
    "gpt-3.5-turbo-16k": [0.003, 0.004],
    "gpt-4": [0.03, 0.06],
    "gpt-4-0301": [0.03, 0.06],
}
