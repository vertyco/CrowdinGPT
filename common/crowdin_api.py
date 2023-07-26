import typing as t

from aiohttp import ClientSession, ClientTimeout

from common.models import QA, Project, String, Translation


class CrowdinAPI:
    def __init__(self, api_key: str):
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.base_url = "https://api.crowdin.com/api/v2"
        self.timeout = ClientTimeout(total=10)

    async def get_projects(self) -> t.List[Project]:
        url = f"{self.base_url}/projects"
        params = {"offset": 0, "limit": 500}
        projects = []
        while True:
            async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url=url, params=params) as res:
                    data = await res.json()
                    if not data:
                        break
                    if not data["data"]:
                        break
                    projects += [Project.parse_obj(i["data"]) for i in data["data"]]
                    params["offset"] += 500
        return projects

    async def get_strings(self, project_id: int) -> t.List[String]:
        url = f"{self.base_url}/projects/{project_id}/strings"
        params = {"offset": 0, "limit": 500}
        sources = []
        while True:
            async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url=url, params=params) as res:
                    data = await res.json()
                    if not data["data"]:
                        break
                    sources += [String.parse_obj(i["data"]) for i in data["data"]]
                    params["offset"] += 500
        return sources

    async def get_qa_issues(self, project_id: int) -> t.List[QA]:
        url = f"{self.base_url}/projects/{project_id}/qa-checks"
        params = {"offset": 0, "limit": 500}
        issues = []
        while True:
            async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url=url, params=params) as res:
                    data = await res.json()
                    if not data["data"]:
                        break
                    issues += [QA.parse_obj(i["data"]) for i in data["data"]]
                    params["offset"] += 500
        return issues

    async def upload_translation(
        self,
        project_id: int,
        string_id: int,
        language_id: int,
        text: str,
    ) -> None:
        url = f"{self.base_url}/projects/{project_id}/translations"
        payload = {"stringId": string_id, "languageId": language_id, "text": text}
        async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.post(url=url, json=payload) as res:
                data = await res.json()
                if res.status == 201:
                    print("Translation uploaded successfully!")
                else:
                    print(f"Upload error (status {res.status}): {data}")

    async def needs_translation(self, project_id: int, string_id: int, language_id: str) -> bool:
        url = f"{self.base_url}/projects/{project_id}/translations"
        params = {"stringId": string_id, "languageId": language_id}
        async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.get(url=url, params=params) as res:
                translations = await res.json()
                if "data" not in translations:
                    print(f"Crowdin translation check error: {translations}")
                    return False
                if not translations["data"]:
                    return True
                if not translations["data"][0]["data"]:
                    return True
                data = translations["data"][0]["data"]
                Translation.parse_obj(data)
                return False

    async def process_qa_issues(
        self,
        project_id: int,
        qa_issues: t.List[QA],
        sources: t.List[String],
        target_langs: t.List[str],
        try_auto_fix: bool = True,
    ) -> None:
        for qa_issue in qa_issues:
            issue_string_id = qa_issue.stringInfo.id
            # Find the source string related to QA issue
            source_string = next(
                (source for source in sources if source.id == issue_string_id), None
            )
            # Find translations in issue languages
            issue_languages = qa_issue.languages
            target_languages = [
                target_lang for target_lang in target_langs if target_lang in issue_languages
            ]

            if source_string is None or not target_languages:
                continue

            issue_type = qa_issue.checkId
            print(
                f"Processing QA Issue {qa_issue.id} - {issue_type} for string '{source_string.text}'"
            )

            for target_lang in target_languages:
                print(f"For target language - {target_lang}")
                # Get original translation
                translation = await get_translation(project_id, issue_string_id, target_lang)

                if translation is None:
                    print("No existing translation found.")
                    continue

                # Attempt auto-fix if possible
                if try_auto_fix:
                    if issue_type == "placeholders":  # If the issue type is placeholders
                        new_translation = auto_fix_placeholder_issue(
                            source_string.text, translation, target_lang
                        )
                    # add more auto-fix for other issue types...
                    else:
                        print(f"No auto fix rule defined for check: {issue_type}")
                        new_translation = None

                    # If auto-fix was successful, update the translation
                    if new_translation is not None:
                        print(f"Auto-fixed translation: {new_translation}")
                        await upload_translation(
                            project_id, source_string.id, target_lang.id, new_translation
                        )
                    else:
                        print("Auto-fix was not successful.")
                else:
                    print("Try auto-fix disabled. Skipping fix.")
