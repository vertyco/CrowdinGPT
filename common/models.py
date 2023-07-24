import typing as t
from datetime import datetime

from pydantic import BaseModel


class Source(BaseModel):
    id: int
    projectId: int
    fileId: int
    branchId: int
    directoryId: int
    identifier: str
    text: str
    type: str
    context: str
    maxLength: int
    isHidden: bool
    isDuplicate: bool
    masterStringId: t.Optional[str] = None
    revision: int
    hasPlurals: bool
    isIcu: bool
    labelIds: list
    createdAt: datetime
    updatedAt: t.Optional[datetime] = None


class Translation(BaseModel):
    id: int
    text: str
    pluralCategoryName: t.Optional[str] = None
    user: dict
    rating: int
    provider: t.Optional[str] = None
    isPreTranslated: bool
    createdAt: datetime


class Language(BaseModel):
    id: str
    name: str
    editorCode: str
    twoLettersCode: str
    threeLettersCode: str
    locale: str
    androidCode: str
    osxCode: str
    osxLocale: str
    pluralCategoryNames: t.List[str]
    pluralRules: str
    pluralExamples: t.List[str]
    textDirection: str
    dialectOf: t.Optional[str]


class Project(BaseModel):
    id: int
    userId: int
    sourceLanguageId: str
    targetLanguageIds: t.List[str]
    languageAccessPolicy: str
    name: str
    cname: t.Optional[str]
    identifier: str
    description: str
    visibility: str
    logo: t.Optional[str]
    publicDownloads: bool
    createdAt: datetime
    updatedAt: datetime
    lastActivity: datetime
    targetLanguages: t.List[Language]
