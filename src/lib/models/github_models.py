from pydantic import BaseModel


class Commit(BaseModel):
    sha: str


class GithubPullRequest(BaseModel):
    """
    This class represents a Github PR
    We've mapped only the fields we need for the sake of simplicity
    """
    head: Commit
    base: Commit


class GithubApp(BaseModel):
    id: int
    slug: str
    name: str


class GithubCheckSuite(BaseModel):
    """
    This class represents a Github Check Suite
    We've mapped only the fields we need for the sake of simplicity
    """
    id: int
    app: GithubApp


class GithubCheckRun(BaseModel):
    """
    This class represents a Github Check Run
    We've mapped only the fields we need for the sake of simplicity
    """
    name: str
    status: str
