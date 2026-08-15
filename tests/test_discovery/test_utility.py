"""Test utility ranks checks by information value, not by hunting 90% confidence."""

from app.discovery.utility import utility_for_marker


def test_mma_outranks_skin_biopsy():
    mma = utility_for_marker("MMA")
    biopsy = utility_for_marker("Skin biopsy if exam and labs remain unexplained")
    assert 0 < biopsy < mma <= 1.0


def test_utility_never_forces_a_hunt_to_ninety():
    for label in ("MMA", "Homocysteine", "EMG/NCS status", "Focused neurologic / sensory exam"):
        score = utility_for_marker(label)
        assert 0.05 <= score <= 1.0
