from __future__ import annotations

from core.identity import canonical_key, same_identity
from core.processing.entity_extractor import EntityExtractor
from simulators.org_ontology import COMPONENTS, PEOPLE, TEAMS, validate_all


def test_canonical_keys_merge_spellings():
    assert canonical_key("Arjun.Sharma") == canonical_key("arjun sharma")
    assert same_identity("arjun_sharma", "Arjun Sharma")


def test_extractor_stub_resolves_ontology_people():
    validate_all()
    ontology = {"people": PEOPLE, "components": COMPONENTS, "teams": TEAMS, "instruments": [], "strategies": []}
    extractor = EntityExtractor(model="test", api_key=None, ontology=ontology)
    result = extractor.extract("Commit by Arjun Sharma touching the orms component.")
    labels = {e["label"] for e in result["entities"]}
    assert "Person" in labels
    assert "Component" in labels
    person = next(e for e in result["entities"] if e["label"] == "Person")
    assert person["props"]["key"] == canonical_key("Arjun Sharma")


def test_extractor_stub_no_false_positives():
    ontology = {"people": PEOPLE, "components": COMPONENTS, "teams": TEAMS, "instruments": [], "strategies": []}
    extractor = EntityExtractor(model="test", api_key=None, ontology=ontology)
    result = extractor.extract("This text mentions no known entity anywhere.")
    assert result["entities"] == []


def test_extractor_detects_incident_ids():
    ontology = {"people": [], "components": [], "teams": {}, "instruments": [], "strategies": []}
    extractor = EntityExtractor(model="test", api_key=None, ontology=ontology)
    result = extractor.extract("Postmortem for INC-0042 is up.")
    incident = next(e for e in result["entities"] if e["label"] == "Incident")
    assert incident["props"]["id"] == "INC-0042"
