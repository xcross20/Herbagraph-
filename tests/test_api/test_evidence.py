import uuid

import pytest

from app.knowledge_graph.food_seed_data import FOOD_INTERVENTIONS, PHYTOCHEMICAL_COMPOUNDS
from app.knowledge_graph.peptide_catalog import PEPTIDE_INTERVENTIONS
from app.knowledge_graph.seed_data import INTERVENTIONS, expected_seeded_intervention_count

pytestmark = pytest.mark.asyncio

TOTAL_SEEDED_INTERVENTIONS = expected_seeded_intervention_count(
    food_interventions=FOOD_INTERVENTIONS,
    phytochemical_compounds=PHYTOCHEMICAL_COMPOUNDS,
    peptide_interventions=PEPTIDE_INTERVENTIONS,
)
HERB_COUNT = sum(1 for i in INTERVENTIONS if i["category"] == "herb")


# ---------------------------------------------------------------------------
# interventions
# ---------------------------------------------------------------------------


async def test_list_interventions_requires_auth(client, seeded_db):
    resp = await client.get("/api/v1/evidence/interventions")
    assert resp.status_code == 401


async def test_list_interventions_returns_all_seeded(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"limit": 200})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == min(TOTAL_SEEDED_INTERVENTIONS, 200)


async def test_list_interventions_default_limit(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions")
    assert resp.status_code == 200
    assert len(resp.json()) == min(TOTAL_SEEDED_INTERVENTIONS, 50)


async def test_list_interventions_filtered_by_category_herb(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"category": "herb", "limit": 200})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == min(HERB_COUNT, 200)
    assert all(i["category"] == "herb" for i in body)


async def test_list_interventions_filtered_by_category_food(authed_client, seeded_db):
    resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"category": "food", "limit": 200}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == min(len(FOOD_INTERVENTIONS), 200)
    assert all(i["category"] == "food" for i in body)


async def test_list_interventions_filtered_by_category_phytochemical(authed_client, seeded_db):
    resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"category": "phytochemical", "limit": 200}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == min(len(PHYTOCHEMICAL_COMPOUNDS), 200)
    assert all(i["category"] == "phytochemical" for i in body)


async def test_list_interventions_search_substring(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"search": "curc"})
    assert resp.status_code == 200
    body = resp.json()
    names = {i["name"] for i in body}
    assert "Curcumin" in names
    curcumin = next(i for i in body if i["name"] == "Curcumin")
    assert curcumin["category"] == "phytochemical"


async def test_list_interventions_search_case_insensitive(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"search": "SULFORAPHANE"})
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()}
    assert "Sulforaphane" in names


async def test_list_interventions_respects_limit(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"limit": 5})
    assert resp.status_code == 200
    assert len(resp.json()) == 5


async def test_list_interventions_limit_over_200_rejected(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"limit": 500})
    assert resp.status_code == 422


async def test_get_intervention_detail_happy_path(authed_client, seeded_db):
    list_resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"search": "Curcumin"}
    )
    intervention_id = list_resp.json()[0]["id"]

    resp = await authed_client.get(f"/api/v1/evidence/interventions/{intervention_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Curcumin"
    assert body["category"] == "phytochemical"
    assert "mechanism" in body
    assert "is_regulated" in body
    assert isinstance(body["safety_flags"], list)
    assert isinstance(body["drug_interactions"], list)


async def test_get_intervention_detail_includes_compounds_with_target(authed_client, seeded_db):
    list_resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"search": "Boswellia serrata"}
    )
    boswellia = next(i for i in list_resp.json() if i["name"] == "Boswellia serrata")
    intervention_id = boswellia["id"]

    resp = await authed_client.get(f"/api/v1/evidence/interventions/{intervention_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["compounds"]) == 1
    compound = body["compounds"][0]["compound"]
    assert "AKBA" in compound["name"]
    assert compound["primary_target"] == "5-LOX"
    assert compound["pubchem_cid"] == 6758


async def test_get_intervention_detail_empty_compounds_for_behavior_intervention(authed_client, seeded_db):
    list_resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"search": "Intermittent Fasting"}
    )
    intervention_id = list_resp.json()[0]["id"]

    resp = await authed_client.get(f"/api/v1/evidence/interventions/{intervention_id}")
    assert resp.status_code == 200
    assert resp.json()["compounds"] == []


async def test_get_intervention_detail_404_for_bad_id(authed_client, seeded_db):
    resp = await authed_client.get(f"/api/v1/evidence/interventions/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_intervention_detail_requires_auth(client, seeded_db):
    resp = await client.get(f"/api/v1/evidence/interventions/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# biomarkers / pathways
# ---------------------------------------------------------------------------


async def test_list_biomarkers_returns_200_plus(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/biomarkers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 200
    names = {b["canonical_name"] for b in body}
    assert "CRP" in names


async def test_list_biomarkers_requires_auth(client, seeded_db):
    resp = await client.get("/api/v1/evidence/biomarkers")
    assert resp.status_code == 401


async def test_list_pathways_returns_28(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/pathways")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 28
    codes = {p["code"] for p in body}
    assert "NF_KB" in codes


async def test_list_pathways_requires_auth(client, seeded_db):
    resp = await client.get("/api/v1/evidence/pathways")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# compounds <-> foods
# ---------------------------------------------------------------------------


async def test_compound_food_sources_sulforaphane(authed_client):
    resp = await authed_client.get("/api/v1/evidence/compounds/Sulforaphane/food-sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["compound"] == "Sulforaphane"
    assert len(body["food_sources"]) >= 4
    food_names = {fs["food"] for fs in body["food_sources"]}
    assert "Broccoli Sprouts" in food_names


async def test_compound_food_sources_unknown_compound_404(authed_client):
    resp = await authed_client.get("/api/v1/evidence/compounds/NotARealCompound/food-sources")
    assert resp.status_code == 404


async def test_compound_food_sources_requires_auth(client):
    resp = await client.get("/api/v1/evidence/compounds/Sulforaphane/food-sources")
    assert resp.status_code == 401


async def test_food_compounds_broccoli_sprouts(authed_client):
    resp = await authed_client.get("/api/v1/evidence/foods/Broccoli Sprouts/compounds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["food"] == "Broccoli Sprouts"
    compound_names = {c["compound"] for c in body["compounds"]}
    assert "Sulforaphane" in compound_names


async def test_food_compounds_unknown_food_404(authed_client):
    resp = await authed_client.get("/api/v1/evidence/foods/NotARealFood/compounds")
    assert resp.status_code == 404


async def test_food_compounds_requires_auth(client):
    resp = await client.get("/api/v1/evidence/foods/Broccoli Sprouts/compounds")
    assert resp.status_code == 401
