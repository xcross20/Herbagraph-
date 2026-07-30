"""IMP-055: graph food sources fallback."""

from app.models.enums import Richness
from app.pipeline.food_source_resolver import attach_food_sources


def test_attach_food_sources_uses_graph_when_catalog_empty():
    sources, compound = attach_food_sources(
        "UnknownPhytoXYZ",
        "phytochemical",
        graph_food_sources=[
            {
                "food_name": "Blueberries",
                "richness": "high",
                "typical_serving": "1 cup",
                "source": "canonical_graph",
            }
        ],
    )
    assert sources is not None
    assert len(sources) == 1
    assert sources[0].food == "Blueberries"
    assert sources[0].richness == Richness.HIGH


def test_catalog_still_preferred_over_graph():
    # Curcumin has static food sources — graph should not replace them when catalog hits
    sources, linked = attach_food_sources(
        "Curcumin",
        "phytochemical",
        graph_food_sources=[{"food_name": "Fake Food", "richness": "low"}],
    )
    assert sources is not None
    assert all(s.food != "Fake Food" for s in sources)
