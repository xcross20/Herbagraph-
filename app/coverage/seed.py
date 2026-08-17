"""In-memory coverage catalog for v0. DB seed is optional."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedTest:
    code: str
    name: str
    modality: str
    specialty: str
    aliases: tuple[str, ...]
    protocols: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SeedRelation:
    test_code: str
    concept: str
    relation: str
    strength: float
    explanation: str
    protocol: str | None = None


CONCEPTS: tuple[tuple[str, str], ...] = (
    ("small_fiber_density", "Intraepidermal small-fiber density"),
    ("large_fiber_function", "Large myelinated fiber / motor unit function"),
    ("structural_brain_lesion", "Structural brain lesion"),
    ("internal_auditory_canal", "Internal auditory canal / skull-base detail"),
    ("cervical_cord", "Cervical cord structure"),
    ("lumbar_cord", "Lumbar / lumbosacral structure"),
    ("cortical_irritability", "Cortical irritability / seizure tendency"),
    ("autonomic_function", "Autonomic function"),
    ("biliary_stones", "Biliary stones / gallbladder structure"),
    ("biliary_ejection", "Gallbladder ejection / biliary dyskinesia"),
    ("abdominal_structure", "Abdominal / pelvic structure"),
    ("gastric_mucosa", "Gastric mucosal inspection"),
    ("colon_mucosa", "Colonic mucosal inspection"),
    ("h_pylori", "H. pylori infection"),
    ("sibo", "Small-intestinal bacterial overgrowth"),
    ("gastric_emptying", "Gastric emptying"),
    ("b12_status", "Vitamin B12 status"),
    ("b12_functional", "Functional B12 / MMA"),
    ("glucose_status", "Glucose / glycemic status"),
    ("thyroid_status", "Thyroid axis"),
    ("iron_status", "Iron / oxygen-delivery status"),
    ("inflammation_signal", "Systemic inflammatory signal"),
    ("autoimmune_serology", "Broad autoimmune serology"),
    ("plasma_protein", "Plasma protein electrophoresis"),
    ("blood_counts", "Blood counts"),
    ("metabolic_panel", "Core metabolic panel"),
)


TESTS: tuple[SeedTest, ...] = (
    SeedTest("emg_ncs", "EMG / nerve conduction study", "electrodiagnostic", "neurology", ("emg", "ncs", "nerve conduction"), (("EMG_NCS_STANDARD", "Standard EMG/NCS"),)),
    SeedTest("mri_brain", "MRI brain", "imaging", "neurology", ("brain mri", "mri head"), (("MRI_BRAIN_STANDARD", "Standard brain MRI"), ("MRI_BRAIN_WWO", "MRI brain with/without contrast"), ("MRI_IAC_WWO", "MRI IAC with/without contrast"), ("MRI_CISS_FIESTA", "CISS/FIESTA skull-base protocol"))),
    SeedTest("mri_cervical", "MRI cervical spine", "imaging", "neurology", ("cervical mri", "c-spine mri"), (("MRI_C_SPINE", "Cervical spine MRI"),)),
    SeedTest("mri_lumbar", "MRI lumbar spine", "imaging", "neurology", ("lumbar mri", "l-spine mri"), (("MRI_L_SPINE", "Lumbar spine MRI"),)),
    SeedTest("eeg", "EEG", "electrodiagnostic", "neurology", ("electroencephalogram",), (("EEG_STANDARD", "Standard EEG"),)),
    SeedTest("ienfd_biopsy", "Skin punch biopsy / IENFD", "pathology", "neurology", ("skin biopsy", "ienfd", "epidermal nerve fiber"), (("IENFD_DISTAL", "Distal-leg IENFD"),)),
    SeedTest("qsart", "QSART", "autonomic", "neurology", ("quantitative sudomotor",), (("QSART_STANDARD", "QSART"),)),
    SeedTest("tilt_table", "Tilt-table test", "autonomic", "neurology", ("tilt table",), (("TILT_STANDARD", "Tilt table"),)),
    SeedTest("autonomic_screen", "Autonomic reflex screen", "autonomic", "neurology", ("autonomic testing", "ars"), (("ARS_STANDARD", "Autonomic reflex screen"),)),
    SeedTest("nerve_biopsy", "Nerve biopsy", "pathology", "neurology", ("sural biopsy",), (("NERVE_BX", "Nerve biopsy"),)),
    SeedTest("ruq_us", "RUQ ultrasound", "imaging", "gastroenterology", ("right upper ultrasound", "gallbladder ultrasound", "abdominal ultrasound"), (("US_RUQ", "Right-upper-quadrant ultrasound"),)),
    SeedTest("ct_abdomen", "CT abdomen/pelvis", "imaging", "gastroenterology", ("ct abd", "ct a/p"), (("CT_AP", "CT abdomen/pelvis"),)),
    SeedTest("hida", "HIDA scan", "imaging", "gastroenterology", ("hida", "hcc scan"), (("HIDA_STANDARD", "HIDA"),)),
    SeedTest("egd", "EGD", "endoscopy", "gastroenterology", ("upper endoscopy", "gastroscopy"), (("EGD_STANDARD", "EGD"),)),
    SeedTest("colonoscopy", "Colonoscopy", "endoscopy", "gastroenterology", ("colo",), (("COLO_STANDARD", "Colonoscopy"),)),
    SeedTest("h_pylori_stool", "H. pylori stool antigen", "lab", "gastroenterology", ("h pylori", "helicobacter"), (("HP_STOOL", "Stool antigen"),)),
    SeedTest("urea_breath", "Urea breath test", "lab", "gastroenterology", ("urea breath",), (("UBT", "Urea breath test"),)),
    SeedTest("sibo_breath", "SIBO breath test", "lab", "gastroenterology", ("sibo", "hydrogen breath"), (("SIBO_H2", "Hydrogen/methane breath"),)),
    SeedTest("gastric_emptying", "Gastric emptying study", "imaging", "gastroenterology", ("ges", "emptying scan"), (("GES_STANDARD", "Gastric emptying"),)),
    SeedTest("cbc", "CBC", "lab", "core", ("complete blood count",), (("CBC", "CBC"),)),
    SeedTest("cmp", "CMP", "lab", "core", ("comprehensive metabolic", "chem 14"), (("CMP", "CMP"),)),
    SeedTest("hba1c", "HbA1c", "lab", "core", ("a1c", "hemoglobin a1c"), (("A1C", "HbA1c"),)),
    SeedTest("glucose", "Fasting glucose", "lab", "core", ("blood sugar", "fasting glucose"), (("GLU", "Glucose"),)),
    SeedTest("insulin", "Fasting insulin", "lab", "core", ("insulin",), (("INS", "Insulin"),)),
    SeedTest("tsh", "TSH", "lab", "core", ("thyroid stimulating",), (("TSH", "TSH"),)),
    SeedTest("free_t4", "Free T4", "lab", "core", ("ft4",), (("FT4", "Free T4"),)),
    SeedTest("b12", "Vitamin B12", "lab", "core", ("cobalamin", "vit b12"), (("B12", "B12"),)),
    SeedTest("mma", "MMA", "lab", "core", ("methylmalonic",), (("MMA", "MMA"),)),
    SeedTest("folate", "Folate", "lab", "core", ("folic acid",), (("FOL", "Folate"),)),
    SeedTest("homocysteine", "Homocysteine", "lab", "core", ("hcy",), (("HCY", "Homocysteine"),)),
    SeedTest("ferritin", "Ferritin", "lab", "core", ("ferritin",), (("FERR", "Ferritin"),)),
    SeedTest("iron_panel", "Iron / TIBC / transferrin saturation", "lab", "core", ("tibc", "iron panel"), (("IRON", "Iron panel"),)),
    SeedTest("vitamin_d", "Vitamin D", "lab", "core", ("25-oh", "25 hydroxy"), (("VITD", "Vitamin D"),)),
    SeedTest("crp", "CRP / hs-CRP", "lab", "core", ("crp", "hs-crp", "hs crp"), (("CRP", "CRP"),)),
    SeedTest("esr", "ESR", "lab", "core", ("sed rate",), (("ESR", "ESR"),)),
    SeedTest("ana", "ANA", "lab", "core", ("antinuclear",), (("ANA", "ANA"),)),
    SeedTest("spep", "SPEP", "lab", "core", ("serum protein electrophoresis",), (("SPEP", "SPEP"),)),
)


RELATIONS: tuple[SeedRelation, ...] = (
    SeedRelation("emg_ncs", "large_fiber_function", "directly_assesses", 0.9, "EMG/NCS primarily evaluates large myelinated peripheral nerve and motor unit function."),
    SeedRelation("emg_ncs", "small_fiber_density", "does_not_directly_assess", 0.96, "EMG/NCS does not measure intraepidermal small-fiber density."),
    SeedRelation("ienfd_biopsy", "small_fiber_density", "directly_assesses", 0.92, "IENFD on punch biopsy is a direct small-fiber structural measure."),
    SeedRelation("qsart", "autonomic_function", "directly_assesses", 0.84, "QSART assesses postganglionic sudomotor function."),
    SeedRelation("qsart", "small_fiber_density", "partially_assesses", 0.6, "Sudomotor testing can support a small-fiber pattern but is not IENFD."),
    SeedRelation("tilt_table", "autonomic_function", "directly_assesses", 0.8, "Tilt-table testing evaluates orthostatic autonomic responses."),
    SeedRelation("autonomic_screen", "autonomic_function", "directly_assesses", 0.88, "An autonomic reflex screen evaluates multiple autonomic domains."),
    SeedRelation("mri_brain", "structural_brain_lesion", "directly_assesses", 0.86, "Standard brain MRI evaluates structural lesions within the included field."),
    SeedRelation("mri_brain", "internal_auditory_canal", "does_not_directly_assess", 0.8, protocol="MRI_BRAIN_STANDARD", explanation="A standard brain MRI may not include dedicated IAC/CISS sequences."),
    SeedRelation("mri_brain", "internal_auditory_canal", "directly_assesses", 0.88, protocol="MRI_IAC_WWO", explanation="Dedicated IAC protocol is designed to evaluate the internal auditory canals."),
    SeedRelation("mri_cervical", "cervical_cord", "directly_assesses", 0.88, "Cervical MRI evaluates cord and canal at cervical levels."),
    SeedRelation("mri_lumbar", "lumbar_cord", "directly_assesses", 0.86, "Lumbar MRI evaluates lumbosacral structure, not brain or small-fiber density."),
    SeedRelation("eeg", "cortical_irritability", "directly_assesses", 0.8, "EEG evaluates cortical electrical irritability, not peripheral small-fiber function."),
    SeedRelation("ruq_us", "biliary_stones", "directly_assesses", 0.86, "RUQ ultrasound looks for gallstones and biliary dilation."),
    SeedRelation("ruq_us", "biliary_ejection", "does_not_directly_assess", 0.9, "Ultrasound structure does not measure gallbladder ejection fraction."),
    SeedRelation("hida", "biliary_ejection", "directly_assesses", 0.88, "HIDA can evaluate biliary excretion and ejection fraction."),
    SeedRelation("ct_abdomen", "abdominal_structure", "directly_assesses", 0.84, "CT abdomen/pelvis evaluates macroscopic abdominal structure."),
    SeedRelation("egd", "gastric_mucosa", "directly_assesses", 0.9, "EGD directly inspects esophageal and gastric mucosa."),
    SeedRelation("colonoscopy", "colon_mucosa", "directly_assesses", 0.9, "Colonoscopy inspects colonic mucosa."),
    SeedRelation("h_pylori_stool", "h_pylori", "directly_assesses", 0.86, "Stool antigen tests for current H. pylori antigen."),
    SeedRelation("urea_breath", "h_pylori", "directly_assesses", 0.86, "Urea breath testing evaluates active H. pylori urease activity."),
    SeedRelation("sibo_breath", "sibo", "partially_assesses", 0.7, "Breath testing can support a SIBO pattern; protocol and prep matter."),
    SeedRelation("gastric_emptying", "gastric_emptying", "directly_assesses", 0.88, "A gastric emptying study measures emptying rate."),
    SeedRelation("b12", "b12_status", "directly_assesses", 0.84, "Serum B12 is a circulating-level measure."),
    SeedRelation("mma", "b12_functional", "directly_assesses", 0.88, "MMA is a functional marker of B12 activity."),
    SeedRelation("hba1c", "glucose_status", "directly_assesses", 0.9, "HbA1c summarizes recent glycemic exposure."),
    SeedRelation("glucose", "glucose_status", "directly_assesses", 0.84, "A glucose value is a point measure of glycemia."),
    SeedRelation("tsh", "thyroid_status", "directly_assesses", 0.86, "TSH is a first-line thyroid-axis marker."),
    SeedRelation("free_t4", "thyroid_status", "directly_assesses", 0.84, "Free T4 complements TSH for thyroid-axis assessment."),
    SeedRelation("cbc", "blood_counts", "directly_assesses", 0.95, "CBC directly reports blood counts."),
    SeedRelation("cmp", "metabolic_panel", "directly_assesses", 0.95, "CMP reports core electrolytes, kidney, and liver analytes."),
    SeedRelation("ferritin", "iron_status", "directly_assesses", 0.82, "Ferritin is a storage-iron marker and also an acute-phase reactant."),
    SeedRelation("iron_panel", "iron_status", "directly_assesses", 0.88, "Iron/TIBC/saturation characterize circulating iron handling."),
    SeedRelation("crp", "inflammation_signal", "directly_assesses", 0.86, "CRP is a systemic inflammatory marker."),
    SeedRelation("esr", "inflammation_signal", "partially_assesses", 0.7, "ESR is a nonspecific inflammatory marker."),
    SeedRelation("ana", "autoimmune_serology", "partially_assesses", 0.7, "ANA is a screening autoantibody, not a disease diagnosis."),
    SeedRelation("spep", "plasma_protein", "directly_assesses", 0.88, "SPEP evaluates plasma protein fractions."),
)


def normalize_alias(raw: str) -> str:
    return " ".join((raw or "").lower().replace("/", " ").replace("-", " ").split())
