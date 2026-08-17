"""Epistemic surface for the coverage/evidence seam.

The live persist mapper is `coverage_to_evidence_relationship`. Do not import
the unaccepted V2 package.
"""

from app.discovery.evidence_mapping import coverage_to_evidence_relationship

__all__ = ["coverage_to_evidence_relationship"]
