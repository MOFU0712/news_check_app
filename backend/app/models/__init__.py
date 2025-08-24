from .user import User
from .article import Article, UserFavorite
from .scraping_job import ScrapingJob
from .prompt import PromptTemplate
from .saved_report import SavedReport

__all__ = [
    "User",
    "Article",
    "UserFavorite", 
    "ScrapingJob",
    "PromptTemplate",
    "SavedReport"
]