import uuid

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# interventions
# ---------------------------------------------------------------------------


async def test_list_interventions_requires_auth(client, seeded_db):
    resp = await client.get("/api/v1/evidence/interventions")
    assert resp.status_code == 401


async def test_list_interventions_returns_all_36(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"limit": 200})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 36


async def test_list_interventions_default_limit(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions")
    assert resp.status_code == 200
    assert len(resp.json()) == 36  # default limit (50) exceeds total seeded count


async def test_list_interventions_filtered_by_category_herb(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"category": "herb"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4
    assert all(i["category"] == "herb" for i in body)


async def test_list_interventions_filtered_by_category_food(authed_client, seeded_db):
    resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"category": "food", "limit": 200}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 13
    assert all(i["category"] == "food" for i in body)


async def test_list_interventions_filtered_by_category_phytochemical(authed_client, seeded_db):
    resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"category": "phytochemical"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 8
    assert all(i["category"] == "phytochemical" for i in body)


async def test_list_interventions_search_substring(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/interventions", params={"search": "curc"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Curcumin"


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
    assert body["category"] == "herb"
    assert "mechanism" in body
    assert "is_regulated" in body
    assert isinstance(body["safety_flags"], list)
    assert isinstance(body["drug_interactions"], list)


async def test_get_intervention_detail_includes_compounds_with_target(authed_client, seeded_db):
    list_resp = await authed_client.get(
        "/api/v1/evidence/interventions", params={"search": "Boswellia"}
    )
    intervention_id = list_resp.json()[0]["id"]

    resp = await authed_client.get(f"/api/v1/evidence/interventions/{intervention_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["compounds"]) == 1
    compound = body["compounds"][0]["compound"]
    assert "AKBA" in compound["name"]
    assert compound["primary_target"] == "5-LOX (5-lipoxygenase)"
    assert compound["pubchem_cid"] is None


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


async def test_list_biomarkers_returns_25(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/biomarkers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 25
    names = {b["canonical_name"] for b in body}
    assert "CRP" in names


async def test_list_biomarkers_requires_auth(client, seeded_db):
    resp = await client.get("/api/v1/evidence/biomarkers")
    assert resp.status_code == 401


async def test_list_pathways_returns_16(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/pathways")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 16
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
    assert len(body["food_sources"]) == 4
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
