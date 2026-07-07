"""Peer-reviewed lifestyle, behavioral, medication-context, hormone, and environmental interventions.

Each entry names a specific validated protocol (not generic category labels). Optional
`methodology_spec` gives dose, duration, and session structure for report narratives.
"""

from __future__ import annotations

_LIFESTYLE_BASE: dict = {
    "is_regulated": False,
    "compounds": [],
    "safety_flags": [],
    "drug_interactions": [],
}

_REGULATED_CONTEXT: dict = {
    "is_regulated": True,
    "regulation_note": "Prescription-only; surfaced for evidence context only, not as a treatment directive.",
    "compounds": [],
    "safety_flags": [],
    "drug_interactions": [],
}

EXERCISE_METHODS: list[dict] = [
    {
        **_LIFESTYLE_BASE,
        "name": "HIIT",
        "category": "exercise",
        "description": "High-intensity interval training for cardiometabolic adaptation.",
        "methodology_spec": (
            "Classic HIIT: 4–6 intervals of 1–4 minutes at 85–95% HRmax with equal or shorter recovery; "
            "3 sessions/week for ≥8 weeks (ACSM-aligned progressive overload)."
        ),
        "mechanism": "Activates AMPK and PGC-1α, improving mitochondrial biogenesis and insulin sensitivity.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Tabata Protocol HIIT",
        "category": "exercise",
        "description": "Ultra-short maximal-effort interval protocol (Tabata et al.).",
        "methodology_spec": (
            "Tabata: 20 seconds maximal effort (≈170% VO₂max on cycle ergometer), 10 seconds rest, "
            "8 rounds (4 minutes total); 4 days/week for 6 weeks."
        ),
        "mechanism": "Supramaximal intervals increase both aerobic and anaerobic capacity via AMPK/mTOR signaling.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Sprint Interval Training",
        "category": "exercise",
        "description": "Repeated short sprints with full recovery (Wingate-style variants in trials).",
        "methodology_spec": (
            "SIT: 4–6 × 30-second all-out sprints with 4-minute recovery; 3 sessions/week for 6–12 weeks."
        ),
        "mechanism": "Rapid glycogen depletion and AMPK activation improve glucose disposal and VO₂peak.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Norwegian 4×4 HIIT",
        "category": "exercise",
        "description": "Four-minute intervals at high aerobic intensity (Helgerud protocol).",
        "methodology_spec": (
            "4 × 4 minutes at 85–95% HRmax with 3-minute active recovery; 3 sessions/week for 8–12 weeks."
        ),
        "mechanism": "Sustained high-intensity aerobic work increases stroke volume and mitochondrial density.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Moderate Continuous Training",
        "category": "exercise",
        "description": "Steady-state aerobic exercise per WHO/ACSM public-health guidelines.",
        "methodology_spec": (
            "150 minutes/week moderate intensity (64–76% HRmax) or 75 minutes vigorous, spread across ≥3 days; "
            "brisk walking, cycling, or swimming."
        ),
        "mechanism": "Improves endothelial function, lipid oxidation, and insulin sensitivity via sustained AMPK activation.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Resistance Training (Progressive Overload)",
        "category": "exercise",
        "description": "Structured resistance exercise for strength and metabolic health.",
        "methodology_spec": (
            "2–3 sessions/week, 6–10 exercises, 2–3 sets of 8–12 reps at 60–80% 1-RM with progressive overload; "
            "ACSM resistance-training guidelines."
        ),
        "mechanism": "Increases skeletal muscle GLUT4 translocation and resting metabolic rate; reduces hepatic fat.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Zone 2 Aerobic Training",
        "category": "exercise",
        "description": "Low-intensity steady-state training below aerobic threshold.",
        "methodology_spec": (
            "45–60 minutes at 60–70% HRmax (conversational pace), 3–5 days/week; "
            "emphasizes fat oxidation and mitochondrial efficiency."
        ),
        "mechanism": "Preferential lipid oxidation and improved mitochondrial respiratory capacity.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Concurrent Aerobic + Resistance Training",
        "category": "exercise",
        "description": "Combined cardio and strength program used in cardiometabolic trials.",
        "methodology_spec": (
            "150 min/week moderate aerobic plus 2 days/week resistance (2 sets × 8–12 reps); "
            "sessions separated by ≥6 hours when possible to limit interference."
        ),
        "mechanism": "Addresses both central hemodynamic and peripheral insulin-sensitizing adaptations.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Low-Volume HIIT",
        "category": "exercise",
        "description": "Time-efficient HIIT with fewer intervals (Gibala-style protocols).",
        "methodology_spec": (
            "10 × 1 minute at ~90% HRmax with 1-minute recovery, 3 sessions/week for 6 weeks; "
            "total vigorous time ≈30 minutes/week."
        ),
        "mechanism": "Brief repeated maximal stimuli improve VO₂peak and insulin sensitivity comparable to higher volumes.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Yoga (Hatha, Structured Sessions)",
        "category": "exercise",
        "description": "Hatha yoga with defined session length used in RCTs for stress and metabolic endpoints.",
        "methodology_spec": (
            "60-minute Hatha yoga sessions, 3–5 days/week for 8–12 weeks; "
            "includes asana, pranayama, and guided relaxation per published trial protocols."
        ),
        "mechanism": "Modulates HPA axis reactivity and parasympathetic tone; may improve lipid and inflammatory markers.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Nordic Walking",
        "category": "exercise",
        "description": "Pole-assisted walking protocol studied for cardiovascular and metabolic outcomes.",
        "methodology_spec": (
            "45-minute Nordic walking at moderate intensity, 3 days/week for 12 weeks; "
            "pole technique per INWA standard to increase upper-body engagement."
        ),
        "mechanism": "Increases energy expenditure vs. walking; improves VO₂peak and upper/lower body endurance.",
    },
]

SLEEP_METHODS: list[dict] = [
    {
        **_LIFESTYLE_BASE,
        "name": "Sleep Hygiene Optimization",
        "category": "sleep",
        "description": "Foundational behavioral sleep practices aligned with CBT-I components.",
        "methodology_spec": (
            "Fixed wake time daily; limit caffeine after 2 PM; no alcohol within 3 hours of bed; "
            "bed reserved for sleep/sex only; 30-minute wind-down without screens; bedroom 65–68°F (18–20°C)."
        ),
        "mechanism": "Strengthens circadian amplitude and reduces hyperarousal that perpetuates insomnia.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Cognitive Behavioral Therapy for Insomnia (CBT-I)",
        "category": "sleep",
        "description": "First-line non-pharmacologic treatment for chronic insomnia (AASM guideline).",
        "methodology_spec": (
            "6–8 weekly sessions (in-person or digital): sleep restriction, stimulus control, "
            "cognitive restructuring, sleep hygiene, and relapse prevention per Perlis/Morin manuals."
        ),
        "mechanism": "Consolidates sleep drive and reduces conditioned arousal; restores normal sleep architecture.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Stimulus Control Therapy",
        "category": "sleep",
        "description": "Core CBT-I component re-associating bed with sleep.",
        "methodology_spec": (
            "Go to bed only when sleepy; leave bed if awake >20 minutes; "
            "return only when sleepy; fixed wake time regardless of sleep duration; no naps."
        ),
        "mechanism": "Breaks bed–wakefulness conditioned association that maintains psychophysiological insomnia.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Sleep Restriction Therapy",
        "category": "sleep",
        "description": "CBT-I component limiting time in bed to match actual sleep time.",
        "methodology_spec": (
            "Restrict time in bed to average total sleep time (minimum 5 hours), "
            "advance by 15–30 minutes when sleep efficiency ≥85% for 5 consecutive nights."
        ),
        "mechanism": "Increases homeostatic sleep drive and consolidates sleep continuity.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Progressive Muscle Relaxation for Sleep",
        "category": "sleep",
        "description": "Jacobson-style PMR before bedtime in insomnia trials.",
        "methodology_spec": (
            "15-minute PMR sequence (tense 5 seconds / release 10 seconds per muscle group) "
            "performed in bed during wind-down, nightly for 4–6 weeks."
        ),
        "mechanism": "Reduces somatic tension and pre-sleep cognitive arousal via parasympathetic activation.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "4-7-8 Breathing for Sleep Onset",
        "category": "sleep",
        "description": "Paced breathing technique used in relaxation-based sleep protocols.",
        "methodology_spec": (
            "Inhale 4 seconds through nose, hold 7 seconds, exhale 8 seconds through mouth; "
            "4 cycles at bedtime and on nocturnal awakenings."
        ),
        "mechanism": "Slow-paced breathing increases vagal tone and reduces sympathetic arousal before sleep.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Bright Light Therapy (Morning)",
        "category": "sleep",
        "description": "Timed light exposure for circadian phase disorders and insomnia comorbidities.",
        "methodology_spec": (
            "10,000 lux white light box within 30 minutes of wake for 20–30 minutes daily, "
            "minimum 5 days/week for 4 weeks (timing adjusted for delayed vs. advanced phase)."
        ),
        "mechanism": "Phase-advances circadian melatonin onset via retinal melanopsin signaling.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Chronotherapy (Fixed Sleep-Wake Schedule)",
        "category": "sleep",
        "description": "Strict sleep-wake timing to entrain circadian rhythm.",
        "methodology_spec": (
            "Identical bed and wake times ±30 minutes daily (including weekends) for ≥4 weeks; "
            "morning outdoor light exposure ≥10 minutes within 1 hour of waking."
        ),
        "mechanism": "Synchronizes suprachiasmatic nucleus oscillation with environmental zeitgebers.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Temperature Regulation for Sleep",
        "category": "sleep",
        "description": "Environmental thermoregulation protocol from sleep medicine literature.",
        "methodology_spec": (
            "Bedroom maintained 65–68°F (18–20°C); warm bath/shower 60–90 minutes before bed "
            "(distal-to-proximal temperature gradient protocol); breathable bedding."
        ),
        "mechanism": "Facilitates core body temperature drop required for sleep onset.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Digital CBT-I (Sleepio/shleep)",
        "category": "sleep",
        "description": "Validated digital delivery of full CBT-I curriculum.",
        "methodology_spec": (
            "6-week structured digital CBT-I: weekly modules covering sleep restriction, stimulus control, "
            "and cognitive therapy with daily sleep diary; 20–30 minutes/day engagement."
        ),
        "mechanism": "Same mechanisms as in-person CBT-I with scalable behavioral adherence support.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Mindfulness-Based Therapy for Insomnia (MBTI)",
        "category": "sleep",
        "description": "Mindfulness adaptation targeting sleep-specific arousal.",
        "methodology_spec": (
            "8 weekly 2-hour group sessions plus daily 20-minute guided body scan or breath meditation; "
            "MBTI manual (Ong/Shapiro protocol)."
        ),
        "mechanism": "Reduces sleep effort and rumination; decouples wakefulness from emotional reactivity.",
    },
]

STRESS_REDUCTION_METHODS: list[dict] = [
    {
        **_LIFESTYLE_BASE,
        "name": "Mindfulness-Based Stress Reduction",
        "category": "stress_reduction",
        "description": "Structured 8-week mindfulness program (Kabat-Zinn MBSR).",
        "methodology_spec": (
            "8 weekly 2.5-hour group sessions + day-long retreat; 45 minutes/day home practice "
            "(body scan, sitting meditation, mindful yoga) per standardized MBSR curriculum."
        ),
        "mechanism": "Reduces HPA axis reactivity and amygdala reactivity; improves interoceptive awareness.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Box Breathing (4-4-4-4)",
        "category": "stress_reduction",
        "description": "Square breathing pattern used in clinical stress-reduction protocols.",
        "methodology_spec": (
            "Inhale 4 seconds, hold 4 seconds, exhale 4 seconds, hold 4 seconds; "
            "repeat for 5 minutes, 2–3 sessions daily."
        ),
        "mechanism": "Paced breathing at ~6 breaths/minute increases heart-rate variability and vagal tone.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "4-7-8 Breathing (Paced Relaxation)",
        "category": "stress_reduction",
        "description": "Dr. Andrew Weil–popularized ratio breathing for acute stress reduction.",
        "methodology_spec": (
            "Inhale 4 seconds, hold 7 seconds, exhale 8 seconds; 4 cycles, repeated 2–4 times daily "
            "or during acute stress episodes."
        ),
        "mechanism": "Extended exhale phase activates parasympathetic nervous system via baroreflex.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Diaphragmatic Breathing (6 breaths/minute)",
        "category": "stress_reduction",
        "description": "Resonance-frequency breathing used in HRV biofeedback research.",
        "methodology_spec": (
            "10 minutes twice daily: inhale 4 seconds, exhale 6 seconds (≈6 breaths/minute) "
            "with diaphragmatic expansion; Lehrer resonance-frequency protocol."
        ),
        "mechanism": "Maximizes heart-rate variability and reduces salivary cortisol in controlled trials.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Transcendental Meditation",
        "category": "stress_reduction",
        "description": "Mantra-based meditation with standardized instruction.",
        "methodology_spec": (
            "20 minutes twice daily, seated with eyes closed, silently repeating assigned mantra; "
            "taught over 4 consecutive days by certified TM instructor."
        ),
        "mechanism": "Reduces cortisol and blood pressure via default-mode network downregulation.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Loving-Kindness Meditation (Metta)",
        "category": "stress_reduction",
        "description": "Structured compassion meditation protocol (Fredrickson/Hofmann trials).",
        "methodology_spec": (
            "15–20 minutes daily: systematic phrases of goodwill toward self, loved one, neutral person, "
            "difficult person, and all beings; 6-week structured program."
        ),
        "mechanism": "Increases positive affect and vagal tone; reduces inflammatory gene expression in trials.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Body Scan Meditation (MBSR)",
        "category": "stress_reduction",
        "description": "Sequential attentional scan through body regions.",
        "methodology_spec": (
            "45-minute guided body scan, daily for 8 weeks during MBSR; "
            "progressive attention from toes to head with non-judgmental awareness."
        ),
        "mechanism": "Improves interoception and reduces rumination-driven HPA activation.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "HRV Biofeedback",
        "category": "stress_reduction",
        "description": "Heart-rate variability biofeedback with resonance breathing.",
        "methodology_spec": (
            "10-minute sessions twice daily at individualized resonance frequency (~5.5–6 breaths/minute) "
            "with HRV monitor feedback; 6–10 weeks per Lehrer/Lehrer protocol."
        ),
        "mechanism": "Trains baroreflex gain and autonomic balance; reduces anxiety and blood pressure.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Yoga Nidra (Guided Deep Relaxation)",
        "category": "stress_reduction",
        "description": "Systematic yogic sleep meditation used in stress RCTs.",
        "methodology_spec": (
            "30–45 minute guided Yoga Nidra practice (rotation of consciousness, breath awareness, "
            "sankalpa intention), 3–5 days/week for 8 weeks."
        ),
        "mechanism": "Shifts autonomic balance toward parasympathetic dominance; reduces perceived stress.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Progressive Muscle Relaxation (Jacobson)",
        "category": "stress_reduction",
        "description": "16-muscle-group tension–release sequence.",
        "methodology_spec": (
            "20-minute sequence: tense each muscle group 5–7 seconds, release 15–20 seconds; "
            "full 16-group Jacobson protocol, daily for 4–8 weeks."
        ),
        "mechanism": "Reduces muscle tension feedback to CNS and lowers sympathetic arousal.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Mindfulness-Based Cognitive Therapy (MBCT)",
        "category": "stress_reduction",
        "description": "8-week MBCT program for stress and depression relapse prevention.",
        "methodology_spec": (
            "8 weekly 2-hour sessions; 45 minutes/day home practice (body scan, sitting meditation, "
            "3-minute breathing space); Segal/Williams MBCT manual."
        ),
        "mechanism": "Decouples negative cognitive rumination from stress physiology via metacognitive awareness.",
    },
]

BEHAVIOR_METHODS: list[dict] = [
    {
        **_LIFESTYLE_BASE,
        "name": "Intermittent Fasting",
        "category": "behavior",
        "description": "Time-restricted eating with defined daily fasting window.",
        "methodology_spec": (
            "16:8 protocol: 8-hour eating window (e.g., 12:00–20:00), 16-hour overnight fast; "
            "5–7 days/week for ≥12 weeks in published metabolic trials."
        ),
        "mechanism": "Activates AMPK and autophagy while suppressing mTOR; improves insulin sensitivity.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "5:2 Intermittent Fasting",
        "category": "behavior",
        "description": "Twice-weekly low-calorie fasting days (Harvie/Harvey protocol).",
        "methodology_spec": (
            "5 normal eating days + 2 non-consecutive fasting days at ~500–600 kcal (women/men); "
            "maintained for ≥12 weeks."
        ),
        "mechanism": "Intermittent caloric restriction improves insulin sensitivity and inflammatory markers.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Alternate-Day Fasting",
        "category": "behavior",
        "description": "Every-other-day modified fasting studied in weight and metabolic trials.",
        "methodology_spec": (
            "Alternate fasting days at ~25% of energy needs (≈500 kcal), "
            "alternating with ad libitum eating days; 8–12 week trials."
        ),
        "mechanism": "Sustained caloric deficit with periodic AMPK activation and ketogenesis on fast days.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Mediterranean Diet (PREDIMED Protocol)",
        "category": "behavior",
        "description": "Mediterranean dietary pattern with EVOO/nuts supplementation.",
        "methodology_spec": (
            "PREDIMED-style: abundant vegetables, legumes, fish, olive oil; "
            "≥4 tbsp EVOO/day or 30 g nuts; limited red meat and processed foods; sustained ≥1 year."
        ),
        "mechanism": "Polyphenol-rich pattern reduces NF-κB activation and improves lipid/inflammatory profiles.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "DASH Diet",
        "category": "behavior",
        "description": "Dietary Approaches to Stop Hypertension eating pattern.",
        "methodology_spec": (
            "8–10 servings fruits/vegetables, 2–3 servings low-fat dairy, whole grains, "
            "≤2,300 mg sodium (1,500 mg for greater BP reduction); maintained ≥8 weeks."
        ),
        "mechanism": "High potassium/magnesium and reduced sodium improve endothelial function and BP.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Low FODMAP Diet (3-Phase Monash)",
        "category": "behavior",
        "description": "Structured FODMAP restriction and reintroduction for IBS.",
        "methodology_spec": (
            "Phase 1: 2–6 weeks strict low FODMAP; Phase 2: systematic 3-day reintroduction challenges; "
            "Phase 3: personalized maintenance per Monash University protocol."
        ),
        "mechanism": "Reduces fermentable substrate load, decreasing visceral hypersensitivity and bloating.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Gluten Elimination Diet",
        "category": "behavior",
        "description": "Strict gluten avoidance for confirmed celiac disease.",
        "methodology_spec": (
            "Complete elimination of wheat, barley, rye, and cross-contaminated oats; "
            "label reading for <20 ppm gluten; dietitian-supervised repletion of iron/B12/D as needed."
        ),
        "mechanism": "Removes gliadin-driven autoimmune intestinal damage and malabsorption in celiac disease.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Early Time-Restricted Eating",
        "category": "behavior",
        "description": "Early-day eating window studied for glycemic and weight outcomes.",
        "methodology_spec": (
            "eTRE: 6–8 hour eating window ending by 15:00 (e.g., 08:00–14:00); "
            "5 days/week for ≥5 weeks in Sutton et al. protocol."
        ),
        "mechanism": "Aligns food intake with circadian insulin sensitivity peak; improves BP and insulin.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Caloric Restriction (25% Deficit)",
        "category": "behavior",
        "description": "Moderate sustained caloric restriction (CALERIE-style).",
        "methodology_spec": (
            "25% caloric deficit from individualized baseline for 12–24 months; "
            "adequate protein (≥0.8 g/kg) and micronutrient repletion per CALERIE trial design."
        ),
        "mechanism": "Reduces mTOR signaling and adiposity; improves cardiometabolic risk markers.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Whole-Food Plant-Based Diet",
        "category": "behavior",
        "description": "Minimally processed plant-predominant dietary pattern.",
        "methodology_spec": (
            "Emphasis on whole grains, legumes, vegetables, fruits, nuts, seeds; "
            "exclude or minimize animal products and ultra-processed foods; ≥8 weeks in trial protocols."
        ),
        "mechanism": "High fiber and polyphenol intake modulates gut microbiome and NF-κB/incretin pathways.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Portfolio Diet",
        "category": "behavior",
        "description": "Combination cholesterol-lowering dietary portfolio (Jenkins).",
        "methodology_spec": (
            "Daily: 2 g plant sterols, 20 g viscous fiber (oats, barley, psyllium), "
            "45 g nuts, 50 g soy protein; maintained ≥4 weeks."
        ),
        "mechanism": "Multiple complementary mechanisms reduce LDL via bile acid binding and HMG-CoA effects.",
    },
]

MEDICATION_CONTEXT: list[dict] = [
    {
        **_REGULATED_CONTEXT,
        "name": "Metformin",
        "category": "medication",
        "description": "First-line oral antidiabetic; evidence context for AMPK pathway discussions.",
        "methodology_spec": "Typical T2DM dosing: start 500 mg once–twice daily with meals, titrate to 1,000–2,000 mg/day per ADA guidelines.",
        "mechanism": "Activates AMPK, reducing hepatic gluconeogenesis and improving peripheral insulin sensitivity.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Atorvastatin",
        "category": "medication",
        "description": "HMG-CoA reductase inhibitor for LDL lowering.",
        "methodology_spec": "10–80 mg once daily; dose per ACC/AHA lipid guidelines based on ASCVD risk.",
        "mechanism": "Inhibits hepatic cholesterol synthesis, upregulating LDL receptor expression.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Lisinopril",
        "category": "medication",
        "description": "ACE inhibitor for hypertension and cardiorenal protection.",
        "methodology_spec": "Start 10 mg daily, titrate to 20–40 mg daily per JNC/ACC hypertension guidelines.",
        "mechanism": "Blocks angiotensin II formation, reducing vasoconstriction and aldosterone secretion.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Losartan",
        "category": "medication",
        "description": "Angiotensin receptor blocker (ARB).",
        "methodology_spec": "50–100 mg once daily per hypertension guidelines; 50 mg starting dose in most adults.",
        "mechanism": "Selective AT1 receptor antagonism reduces vasoconstriction and cardiac remodeling.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Empagliflozin",
        "category": "medication",
        "description": "SGLT2 inhibitor with cardiovascular outcome trial data.",
        "methodology_spec": "10 mg once daily, may increase to 25 mg; per ADA/EASD T2DM and heart-failure guidelines.",
        "mechanism": "Inhibits renal SGLT2, inducing glucosuria and reducing preload/afterload.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Omeprazole",
        "category": "medication",
        "description": "Proton pump inhibitor for GERD and ulcer disease.",
        "methodology_spec": "20–40 mg once daily before breakfast for 4–8 weeks (GERD); long-term use requires clinician oversight.",
        "mechanism": "Irreversibly inhibits gastric H+/K+ ATPase, reducing acid secretion.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Sertraline",
        "category": "medication",
        "description": "SSRI antidepressant with anxiety indications.",
        "methodology_spec": "Start 25–50 mg daily, titrate to 50–200 mg/day per APA depression/anxiety guidelines.",
        "mechanism": "Selective serotonin reuptake inhibition increases synaptic 5-HT availability.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Levothyroxine",
        "category": "medication",
        "description": "Synthetic T4 replacement for hypothyroidism.",
        "methodology_spec": "1.6 mcg/kg/day typical full replacement; take fasting 30–60 min before food; titrate by TSH.",
        "mechanism": "Restores euthyroid state via T4→T3 conversion and nuclear thyroid receptor signaling.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Low-Dose Aspirin",
        "category": "medication",
        "description": "Antiplatelet therapy for select ASCVD primary/secondary prevention.",
        "methodology_spec": "81 mg daily in select high-risk adults per USPSTF/ACC guidance; bleeding risk assessment required.",
        "mechanism": "Irreversible COX-1 inhibition reduces thromboxane A2-mediated platelet aggregation.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Warfarin",
        "category": "medication",
        "description": "Vitamin K antagonist anticoagulant.",
        "methodology_spec": "Dose adjusted to INR target (typically 2.0–3.0 for AF/VTE); daily dosing with INR monitoring.",
        "mechanism": "Inhibits vitamin K epoxide reductase, reducing functional clotting factors II, VII, IX, X.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Ezetimibe",
        "category": "medication",
        "description": "NPC1L1 inhibitor adjunct for LDL lowering.",
        "methodology_spec": "10 mg once daily, alone or with statin, per ACC/AHA lipid guidelines.",
        "mechanism": "Blocks intestinal cholesterol absorption via NPC1L1 transporter.",
    },
]

HORMONE_CONTEXT: list[dict] = [
    {
        **_REGULATED_CONTEXT,
        "name": "GLP-1 Receptor Agonists (Class)",
        "category": "hormone",
        "description": "Incretin hormone class including semaglutide, liraglutide, dulaglutide.",
        "methodology_spec": (
            "Subcutaneous GLP-1 RA per agent label (e.g., semaglutide 2.4 mg weekly for obesity after titration); "
            "physician-supervised dose escalation over 16–20 weeks."
        ),
        "mechanism": "GLP-1 receptor activation enhances glucose-dependent insulin secretion and slows gastric emptying.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "GLP-1/GIP Dual Agonists (Class)",
        "category": "hormone",
        "description": "Dual incretin agonist class (tirzepatide).",
        "methodology_spec": (
            "Tirzepatide: start 2.5 mg weekly SC, escalate by 2.5 mg every 4 weeks to 5–15 mg "
            "per SURPASS/SURMOUNT trial titration schedules."
        ),
        "mechanism": "Co-activation of GIP and GLP-1 receptors amplifies incretin-mediated glycemic and weight effects.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Testosterone Replacement Therapy",
        "category": "hormone",
        "description": "Exogenous testosterone for confirmed male hypogonadism.",
        "methodology_spec": (
            "Gel 1–1.62% daily or IM injection per Endocrine Society guidelines; "
            "target mid-normal physiologic range with hematocrit and PSA monitoring."
        ),
        "mechanism": "Androgen receptor activation restores lean mass, libido, and erythropoiesis in hypogonadism.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Estradiol Hormone Therapy",
        "category": "hormone",
        "description": "Menopausal estrogen therapy for vasomotor symptoms.",
        "methodology_spec": (
            "Lowest effective transdermal estradiol (0.025–0.05 mg/day patch) or oral equivalent "
            "per NAMS 2022 hormone therapy position statement; annual risk review."
        ),
        "mechanism": "Estrogen receptor signaling in hypothalamus reduces vasomotor symptoms and bone resorption.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Somatropin (Growth Hormone)",
        "category": "hormone",
        "description": "Recombinant GH for GH deficiency and approved indications.",
        "methodology_spec": "Weight-based daily SC dosing (typically 0.2–0.4 mg/day adult GHD); IGF-1–guided titration.",
        "mechanism": "GH receptor activation stimulates IGF-1 production, lipolysis, and protein anabolism.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Desiccated Thyroid (NDT)",
        "category": "hormone",
        "description": "Porcine thyroid extract containing T4 and T3.",
        "methodology_spec": "Start low (e.g., 30 mg Armour) and titrate by symptoms and TSH/free T4; once-daily dosing.",
        "mechanism": "Provides combined T4/T3 replacement for hypothyroidism in selected patients.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Progesterone (Bioidentical)",
        "category": "hormone",
        "description": "Micronized progesterone for endometrial protection with estrogen therapy.",
        "methodology_spec": "200 mg micronized progesterone at bedtime for 12 days/cycle or continuous combined HT per NAMS.",
        "mechanism": "Progesterone receptor activation protects endometrium and modulates GABA-A for sleep.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "DHEA Supplementation",
        "category": "hormone",
        "description": "Adrenal androgen precursor studied in adrenal insufficiency and aging.",
        "methodology_spec": "25–50 mg daily in adrenal insufficiency trials; morning dosing with DHEA-S monitoring.",
        "mechanism": "Peripheral conversion to androgens and estrogens; restores adrenal androgen milieu.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Insulin (Basal-Bolus Regimen)",
        "category": "hormone",
        "description": "Exogenous insulin for diabetes management.",
        "methodology_spec": (
            "Basal insulin (glargine/detemir/degludec) once daily plus prandial rapid-acting insulin "
            "per ADA intensive insulin protocol; individualized carb-ratio dosing."
        ),
        "mechanism": "Direct activation of insulin receptor tyrosine kinase, promoting glucose uptake and storage.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Combined Oral Contraceptives",
        "category": "hormone",
        "description": "Estrogen–progestin combination for contraception and cycle regulation.",
        "methodology_spec": "Typical 20–35 mcg ethinyl estradiol + progestin, 21 active + 7 placebo days; daily same-time dosing.",
        "mechanism": "Suppresses gonadotropin surge via negative feedback, preventing ovulation.",
    },
    {
        **_REGULATED_CONTEXT,
        "name": "Hydrocortisone (Physiologic Replacement)",
        "category": "hormone",
        "description": "Glucocorticoid replacement for adrenal insufficiency.",
        "methodology_spec": (
            "15–25 mg/day divided (e.g., 10 mg AM + 5 mg early PM) or continuous-release preparation "
            "per Endocrine Society adrenal insufficiency guidelines."
        ),
        "mechanism": "Activates glucocorticoid receptors, restoring cortisol-dependent metabolic and stress responses.",
    },
]

ENVIRONMENTAL_METHODS: list[dict] = [
    {
        **_LIFESTYLE_BASE,
        "name": "HEPA Air Filtration",
        "category": "environmental",
        "description": "Portable HEPA filtration for indoor particulate reduction.",
        "methodology_spec": (
            "True HEPA (≥99.97% at 0.3 µm) portable unit sized to room CADR; "
            "run continuously in bedroom and main living area; filter replacement per manufacturer."
        ),
        "mechanism": "Reduces PM2.5 exposure, lowering systemic inflammatory and respiratory burden.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Indoor PM2.5 Reduction Protocol",
        "category": "environmental",
        "description": "Multi-component indoor air quality improvement.",
        "methodology_spec": (
            "HEPA filtration + eliminate indoor smoking/vaping + ventilate during cooking; "
            "target indoor PM2.5 <12 µg/m³ per EPA/WHO guidance."
        ),
        "mechanism": "Lower particulate load reduces oxidative stress and NF-κB activation in airway and systemic tissues.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Mold Remediation (Professional)",
        "category": "environmental",
        "description": "Source removal and moisture control for water-damaged buildings.",
        "methodology_spec": (
            "Identify moisture source; professional remediation per EPA/IICRC S520; "
            "maintain indoor humidity 30–50%; post-remediation air testing."
        ),
        "mechanism": "Removes mycotoxin and spore exposure driving respiratory inflammation and sensitization.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Low-VOC Interior Environment",
        "category": "environmental",
        "description": "Reduction of volatile organic compound off-gassing indoors.",
        "methodology_spec": (
            "Use low-VOC paints, furnishings, and cleaners; increase ventilation 15 minutes 3× daily; "
            "avoid air fresheners and unvented combustion."
        ),
        "mechanism": "Reduces inhaled VOC burden that contributes to airway irritation and oxidative stress.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Nature Exposure (120 min/week)",
        "category": "environmental",
        "description": "Green-space exposure dose from UK nature-health research.",
        "methodology_spec": (
            "≥120 minutes/week in natural environments (parks, forests, coast) in sessions ≥20 minutes; "
            "White et al. dose–response threshold."
        ),
        "mechanism": "Reduces perceived stress and blood pressure via attention restoration and reduced rumination.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Morning Daylight Exposure",
        "category": "environmental",
        "description": "Outdoor morning light for circadian entrainment.",
        "methodology_spec": (
            "≥10–30 minutes outdoor daylight within 1 hour of waking, without sunglasses when safe; "
            "daily including overcast days."
        ),
        "mechanism": "Melanopsin-mediated phase advance of circadian melatonin rhythm.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Noise Reduction for Sleep",
        "category": "environmental",
        "description": "Environmental noise mitigation for sleep quality.",
        "methodology_spec": (
            "Bedroom noise <30 dB(A) overnight; earplugs or white-noise masking at 40–50 dB if ambient noise unavoidable."
        ),
        "mechanism": "Reduces sleep fragmentation and cortisol spikes from nocturnal noise events.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Water Filtration (Carbon + RO)",
        "category": "environmental",
        "description": "Point-of-use filtration for drinking water contaminants.",
        "methodology_spec": (
            "NSF-certified activated carbon block plus reverse-osmosis for drinking/cooking water; "
            "filter changes per manufacturer schedule."
        ),
        "mechanism": "Reduces heavy metals, disinfection byproducts, and microplastics in oral exposure route.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Radon Mitigation",
        "category": "environmental",
        "description": "Sub-slab depressurization for elevated indoor radon.",
        "methodology_spec": (
            "Test with long-term alpha-track detector; if ≥4 pCi/L, install active sub-slab depressurization "
            "per EPA mitigation standards; retest post-installation."
        ),
        "mechanism": "Reduces alpha-particle radiation exposure linked to lung cancer risk.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Thermal Comfort Optimization",
        "category": "environmental",
        "description": "Indoor thermal environment management for health and sleep.",
        "methodology_spec": (
            "Maintain indoor operative temperature 68–76°F (20–24°C) for daytime activity; "
            "62–68°F (17–20°C) for sleep per ASHRAE comfort standards."
        ),
        "mechanism": "Thermal comfort reduces sympathetic activation and supports sleep-initiation thermoregulation.",
    },
    {
        **_LIFESTYLE_BASE,
        "name": "Blue-Light Reduction (Evening)",
        "category": "environmental",
        "description": "Evening light hygiene for circadian protection.",
        "methodology_spec": (
            "Dim overhead lights 2 hours before bed; enable device night mode; "
            "amber/blue-blocking glasses if screen use necessary after sunset."
        ),
        "mechanism": "Reduces melanopsin-mediated circadian phase delay from evening blue-enriched light.",
    },
]

LIFESTYLE_INTERVENTIONS: list[dict] = (
    EXERCISE_METHODS
    + SLEEP_METHODS
    + STRESS_REDUCTION_METHODS
    + BEHAVIOR_METHODS
    + MEDICATION_CONTEXT
    + HORMONE_CONTEXT
    + ENVIRONMENTAL_METHODS
)

METHODOLOGY_BY_NAME: dict[str, str] = {
    entry["name"]: entry["methodology_spec"]
    for entry in LIFESTYLE_INTERVENTIONS
    if entry.get("methodology_spec")
}

LIFESTYLE_CATEGORIES = {
    "exercise", "sleep", "stress_reduction", "behavior",
    "medication", "hormone", "environmental",
}