# Crowdin GPT Translator

This project uses OpenAI's GPT models to translate strings for a Crowdin project. While doing translations, it ensures the preservation of Python string formatting and makes optimal use of function calls for the sake of accuracy.

## Setup And Installation

Before running the script, you will need to clone the repo and install a few Python packages.

Clone the repo:

```
git clone https://github.com/vertyco/CrowdinGPT.git
```

Install the required packages using pip:

```sh
pip install -r requirements.txt
```

You will also need to set up the environment variables. Do the following:

1. Create a `.env` file in the root directory of your project.
2. Add the lines below in the `.env` file, replacing `YOUR_OPENAI_KEY` and `YOUR_CROWDIN_KEY` with your actual keys:

```sh
OPENAI_KEY=YOUR_OPENAI_KEY
CROWDIN_KEY=YOUR_CROWDIN_KEY

# Optional
AUTO = 0  # Enables full automation when set to 1, requires confirmation when set to 0.
ENDPOINT_OVERRIDE = "http://localhost:8000/v1"  # Useful for self-hosted models

# Additional Optional Keys
DEEPL_KEY = YOUR_DEEPL_KEY  # Insert your DeepL key if available
MODEL = "gpt-3.5-turbo"  # Specify the GPT model to use, defaults to "gpt-3.5-turbo" if not provided
PRE_TRANSLATE = 1  # Set to 1 to enable pre-translation, 0 to disable. Disabled by default.
```

## Running the Script

You can run the script with the following command:

```sh
python crowdingpt.py
```

## How It Works

The script first retrieves all the strings of a project from the Crowdin platform. Then, it translates each string that does not already have a translation in the target language. The translation process respects the formatting and placeholders such as `{}` and ``` of the original string. The script also breaks down lengthy strings into smaller parts for translation to help with formatting.

## Contributions

Contributions to this repository are welcome. You can fork the repository and create a pull request with your changes.

## Disclaimer

This project is meant for experimental usage and not for commercial purposes. Translations depend highly on the quality of the GPT model and accuracy of the Google Translate API. For official translations, consider using professional translation services.

## Contact

If you encounter any issues or have any questions about this project, please open an issue on this GitHub repository.
