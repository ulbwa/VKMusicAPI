from dataclasses import dataclass


@dataclass
class Account:
    login: str
    password: str


@dataclass
class SearchResult:
    id: str
    artist: str
    title: str
    duration: int
    url: str


@dataclass
class DownloadResult:
    id: str
    artist: str
    title: str
    duration: int
    file: str
