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
    ) -> dict:
        url = f"{self.base_url}/projects/{project_id}/translations"
        payload = {"stringId": string_id, "languageId": language_id, "text": text}
        async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.post(url=url, json=payload) as res:
                data = await res.json()
                if res.status == 201:
                    print("Translation uploaded successfully!")
                else:
                    print(f"Upload error (status {res.status}): {data}")
                return data

    async def needs_translation(
        self,
        project_id: int,
        string_id: int,
        language_id: str,
    ) -> t.Optional[Translation]:
        url = f"{self.base_url}/projects/{project_id}/translations"
        params = {"stringId": string_id, "languageId": language_id}
        async with ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.get(url=url, params=params) as res:
                translations = await res.json()
                if "data" not in translations:
                    print(f"Crowdin translation check error: {translations}")
                    return
                if not translations["data"]:
                    return
                if not translations["data"][0]["data"]:
                    return
                return Translation.parse_obj(translations["data"][0]["data"])
