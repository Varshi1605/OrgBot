from __future__ import annotations

import pytest

from core.identity import canonical_key, github_handle, same_identity, slack_handle
from simulators.org_ontology import (
    PEOPLE,
    TEAMS,
    get_person,
    people_for_team,
    validate_all,
)


def test_ontology_has_expected_shape():
    assert len(PEOPLE) == 20
    assert len(TEAMS) == 5
    for team in TEAMS.values():
        assert len(team["members"]) == 4


def test_validate_all_passes():
    validate_all()


def test_validate_all_rejects_unknown_person():
    with pytest.raises(ValueError):
        get_person("Not An Engineer")


def test_people_for_team_returns_four():
    for team_id in TEAMS:
        assert len(people_for_team(team_id)) == 4


def test_identity_normalization():
    assert canonical_key("Arjun Sharma") == "arjunsharma"
    assert github_handle("Arjun Sharma") == slack_handle("Arjun Sharma")
    assert same_identity("arjun.sharma", "Arjun Sharma")
    assert not same_identity("Arjun Sharma", "Priya Nair")
