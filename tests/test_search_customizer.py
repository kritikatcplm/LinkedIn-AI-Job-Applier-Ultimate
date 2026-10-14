"""Tests for src/job_manager/search_customizer.py"""

from unittest.mock import MagicMock

import pytest

from config.constants import SEARCH_CONFIG_FILE
from src.job_manager.linkedin.search_customizer_linkedin import (
    SearchCustomizer as LinkedInSearchCustomizer,
)
from src.job_manager.search_customizer import BaseSearchCustomizer
from src.pydantic_models.config_models import SearchConfig
from src.utils.utils import load_yaml_file


class ConcreteSearchCustomizer(BaseSearchCustomizer):
    """Minimal concrete implementation for testing BaseSearchCustomizer methods."""

    async def set_search_params(self):
        pass


@pytest.fixture
def customizer():
    return ConcreteSearchCustomizer(page=MagicMock())


class TestSearchCustomizerInit:
    def test_default_attributes(self, customizer):
        assert customizer.positions == []
        assert customizer.locations == []
        assert customizer.remote is False
        assert customizer.onsite is False
        assert customizer.hybrid is False
        assert customizer.experience_level == {}
        assert customizer.job_types == {}
        assert customizer.date_posted == {}
        assert customizer.apply_once_at_company is True
        assert customizer.company_blacklist == []
        assert customizer.title_blacklist == []
        assert customizer.location_blacklist == []


class TestSetAdvancedSearchParams:
    def test_sets_all_params(self, customizer):
        params = {
            "positions": ["Software Engineer", "Backend Developer"],
            "locations": ["New York", "Remote"],
            "remote": True,
            "onsite": False,
            "hybrid": True,
            "experience_level": {"mid": True, "senior": True},
            "job_types": {"full_time": True},
            "date": {"month": True},
            "apply_once_at_company": False,
            "company_blacklist": ["BadCorp"],
            "title_blacklist": ["intern"],
            "location_blacklist": ["Antarctica"],
        }

        customizer.set_advanced_search_params(params)

        assert customizer.positions == ["Software Engineer", "Backend Developer"]
        assert customizer.locations == ["New York", "Remote"]
        assert customizer.remote is True
        assert customizer.hybrid is True
        assert customizer.onsite is False
        assert customizer.apply_once_at_company is False
        assert customizer.company_blacklist == ["BadCorp"]
        assert customizer.title_blacklist == ["intern"]
        assert customizer.location_blacklist == ["Antarctica"]

    def test_defaults_for_optional_params(self, customizer):
        customizer.set_advanced_search_params({"positions": ["Engineer"]})

        assert customizer.remote is False
        assert customizer.onsite is False
        assert customizer.hybrid is False
        assert customizer.apply_once_at_company is True
        assert customizer.company_blacklist == []

    def test_none_list_params_default_to_empty_lists(self, customizer):
        customizer.set_advanced_search_params(
            {
                "positions": ["Engineer"],
                "locations": None,
                "company_blacklist": None,
                "title_blacklist": None,
                "location_blacklist": None,
            }
        )

        assert customizer.locations == []
        assert customizer.company_blacklist == []
        assert customizer.title_blacklist == []
        assert customizer.location_blacklist == []


class TestIsJobBlacklisted:
    def test_title_blacklisted(self, customizer):
        customizer.title_blacklist = ["intern", "junior"]
        assert customizer.is_job_blacklisted("Junior Developer", "GoodCorp", "New York") is True

    def test_title_blacklist_case_insensitive(self, customizer):
        customizer.title_blacklist = ["INTERN"]
        assert customizer.is_job_blacklisted("Software Intern", "GoodCorp", "New York") is True

    def test_company_blacklisted(self, customizer):
        customizer.company_blacklist = ["BadCorp"]
        assert customizer.is_job_blacklisted("Engineer", "BadCorp Inc", "New York") is True

    def test_company_blacklist_case_insensitive(self, customizer):
        customizer.company_blacklist = ["badcorp"]
        assert customizer.is_job_blacklisted("Engineer", "BADCORP", "New York") is True

    def test_location_blacklisted(self, customizer):
        customizer.location_blacklist = ["Antarctica"]
        assert customizer.is_job_blacklisted("Engineer", "GoodCorp", "Antarctica Base") is True

    def test_location_blacklist_case_insensitive(self, customizer):
        customizer.location_blacklist = ["ANTARCTICA"]
        assert customizer.is_job_blacklisted("Engineer", "GoodCorp", "antarctica") is True

    def test_not_blacklisted(self, customizer):
        customizer.title_blacklist = ["intern"]
        customizer.company_blacklist = ["BadCorp"]
        customizer.location_blacklist = ["Antarctica"]
        assert customizer.is_job_blacklisted("Senior Engineer", "GoodCorp", "New York") is False

    def test_empty_blacklists(self, customizer):
        assert customizer.is_job_blacklisted("Any Title", "Any Corp", "Any Location") is False

    def test_partial_title_match(self, customizer):
        customizer.title_blacklist = ["sales"]
        assert customizer.is_job_blacklisted("Sales Manager", "Corp", "NY") is True
        assert customizer.is_job_blacklisted("Software Engineer", "Corp", "NY") is False


class TestConfiguredGeoStrategy:
    """Verify the configured SAP MM geography strategy in config/search_config.yaml.

    Requirement: office jobs in Austria, remote-only everywhere else, plus a
    worldwide remote pass for any other country.
    """

    @pytest.fixture
    def params(self):
        return SearchConfig(**load_yaml_file(SEARCH_CONFIG_FILE)).model_dump()

    @staticmethod
    def _pass_for(params, location_name):
        return next(
            passed
            for passed in params["search_passes"]
            if str(passed.get("location", "")).lower() == location_name
        )

    def test_austria_pass_allows_office_work(self, customizer, params):
        customizer.set_advanced_search_params(params)

        customizer.activate_pass(self._pass_for(params, "austria"))

        assert customizer.locations == ["Austria"]
        assert customizer.remote is True
        assert customizer.hybrid is True
        assert customizer.onsite is True

    def test_every_other_region_is_remote_only(self, customizer, params):
        customizer.set_advanced_search_params(params)

        non_austria = [
            passed
            for passed in params["search_passes"]
            if str(passed.get("location", "")).lower() != "austria"
        ]

        assert len(non_austria) >= 3
        for passed in non_austria:
            customizer.activate_pass(passed)
            assert customizer.remote is True
            assert customizer.hybrid is False
            assert customizer.onsite is False

    def test_worldwide_pass_clears_location_for_any_country(self, customizer, params):
        customizer.set_advanced_search_params(params)

        # Start from a concrete location so we prove the worldwide pass resets it.
        customizer.activate_pass({"location": "Austria", "remote": True})
        assert customizer.locations == ["Austria"]

        worldwide = next(
            passed for passed in params["search_passes"] if passed.get("locations") == []
        )
        customizer.activate_pass(worldwide)

        assert customizer.locations == []
        assert customizer.remote is True
        assert customizer.hybrid is False
        assert customizer.onsite is False

    def test_search_terms_are_sap_mm_focused(self, params):
        linkedin_customizer = LinkedInSearchCustomizer(MagicMock())
        linkedin_customizer.set_advanced_search_params(params)

        query = linkedin_customizer.format_linkedin_keyword_query()

        assert '"SAP MM"' in query
        assert "SAP Materials Management" in query
        assert query.count('" OR "') >= 4

    def test_multiple_roles_per_company_are_allowed(self, customizer, params):
        customizer.set_advanced_search_params(params)

        assert customizer.apply_once_at_company is False
