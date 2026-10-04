"""
Abstract base class for job-site search customizers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Union

from playwright.sync_api import Page

from config.logger_config import logger
from src.dashboard.runtime import emit_event


class BaseSearchCustomizer(ABC):
    def __init__(self, page: Union[Page, Any]):
        self.page = page
        self.positions = []
        self.locations = []
        self.remote = False
        self.onsite = False
        self.hybrid = False
        self.experience_level = {}
        self.job_types = {}
        self.date_posted = {}
        self.apply_once_at_company = True
        self.company_blacklist = []
        self.title_blacklist = []
        self.location_blacklist = []
        self.search_passes = []
        self._full_parameters = {}

    def set_advanced_search_params(self, parameters: Dict[str, Any]) -> None:
        """Set search parameters from config"""
        logger.info(f"Setting {self.__class__.__name__} parameters")
        self.positions = parameters["positions"]
        self.remote = parameters.get("remote", False)
        self.onsite = parameters.get("onsite", False)
        self.hybrid = parameters.get("hybrid", False)
        self.experience_level = parameters.get("experience_level", {})
        self.job_types = parameters.get("job_types", {})
        self.date_posted = parameters.get("date", {})
        self.locations = parameters.get("locations") or []
        self.apply_once_at_company = parameters.get("apply_once_at_company", True)
        self.company_blacklist = parameters.get("company_blacklist") or []
        self.title_blacklist = parameters.get("title_blacklist") or []
        self.location_blacklist = parameters.get("location_blacklist") or []
        self.search_passes = parameters.get("search_passes") or []
        self._full_parameters = dict(parameters)
        logger.info(f"{self.__class__.__name__} parameters successfully set")

    def activate_pass(self, pass_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Apply one search-pass configuration and return the merged parameters."""
        if not isinstance(pass_cfg, dict):
            return dict(self._full_parameters)

        location = pass_cfg.get("location")
        if location is None:
            location = pass_cfg.get("locations")
        if isinstance(location, str):
            self.locations = [location]
        elif isinstance(location, list):
            self.locations = [str(item) for item in location if item]

        self.remote = bool(pass_cfg.get("remote", False))
        self.hybrid = bool(pass_cfg.get("hybrid", False))
        self.onsite = bool(pass_cfg.get("onsite", False))

        merged = dict(self._full_parameters)
        merged["locations"] = self.locations
        merged["remote"] = self.remote
        merged["hybrid"] = self.hybrid
        merged["onsite"] = self.onsite
        return merged

    def is_job_blacklisted(self, job_title: str, company_name: str, job_location: str) -> bool:
        """Return True if this job should be skipped based on blacklists"""
        title_lower = job_title.lower()
        company_lower = company_name.lower()
        location_lower = job_location.lower()

        for blacklisted in self.title_blacklist:
            if blacklisted.lower() in title_lower:
                logger.info(f"Job '{job_title}' skipped - title blacklisted: {blacklisted}")
                return True

        for blacklisted in self.company_blacklist:
            if blacklisted.lower() in company_lower:
                logger.info(f"Job at '{company_name}' skipped - company blacklisted: {blacklisted}")
                return True

        for blacklisted in self.location_blacklist:
            if blacklisted.lower() in location_lower:
                logger.info(
                    f"Job in '{job_location}' skipped - location blacklisted: {blacklisted}"
                )
                return True

        return False

    @abstractmethod
    async def set_search_params(self) -> None:
        """Navigate to and configure the job search page"""
        pass
