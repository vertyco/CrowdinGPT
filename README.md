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

In addition, you have to set up the environment variables:

1. Create a `.env` file in the root directory of the project
2. In the `.env` file, add the following lines and replace `YOUR_OPENAI_KEY` and `YOUR_CROWDIN_KEY` with your actual keys:

```sh
OPENAI_KEY=YOUR_OPENAI_KEY
CROWDIN_KEY=YOUR_CROWDIN_KEY

# Optional
AUTO = 0  # 1 for full auto, 0 asks for confirmation
ENDPOINT_OVERRIDE = "http://localhost:8000/v1"  # For self-hosted LLMs
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

This project is meant for experimental usage and not for commercial purposes. Translations depend highly on the quality of the GPT model and accuracy of the google translate API. For official translations, consider using professional translation services.

## Contact

If you encounter any issues or have any questions about this project, please open an issue on this GitHub repository.
