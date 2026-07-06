# Scope of the Living Review

This document is the single source of truth for what belongs in the
Living Review of ML/AI for Particle Accelerators. It is applied by the
automated adjudicator (its hypothesis string is derived from the criterion
below), by human curators reviewing the pending queue, and by contributors
submitting papers. When a borderline case is resolved, add it to the
worked examples — this file accretes precedent.

## The criterion: does the ML touch the machine or the beam?

> **In scope** if the machine learning / AI models, controls, optimizes,
> or diagnoses the *accelerator, the beamline, or the beam itself* —
> regardless of what the facility is for (research, light source, medical,
> industrial).
>
> **Out of scope** if the accelerator only appears upstream as the tool
> that produced the data, and the ML operates purely on the *downstream
> product* (image, sample, patient outcome, detector event) — and, of
> course, if there is no particle accelerator at all.

The canonical adjudicator hypothesis:

> "This paper applies machine learning or artificial intelligence to a
> particle accelerator, beamline, or particle beam."

## Worked examples

### In scope

| Paper topic | Why |
|---|---|
| RL tuning of the LCLS linac to maximize FEL pulse energy | Beam/machine control |
| Neural-network surrogate of injector beam dynamics | Models the machine |
| Anomaly detection on CEBAF RF cavity fault signals | Diagnoses the machine |
| ML prediction of pencil-beam-scanning spot positions from proton-therapy delivery logs | Beam delivery control — a medical facility is still an accelerator |
| Autoencoder monitoring of daily medical-linac QA / dosimetric drift | Machine QA of a clinical linac |
| Bayesian optimization of synchrotron beamline optics alignment | Beamline control at a light source |
| ML-based virtual diagnostics of bunch length / beam phase space | Beam diagnostics |
| Surrogate models for laser/plasma wakefield acceleration | Beam physics (advanced accelerator concepts) |
| 1990s neural-network orbit correction at storage rings | Founding literature of this field |
| ML surrogate for neutron-shielding / radiation-safety design of an accelerator facility | Machine-tied facility infrastructure (decided 2026-07 during the model benchmark) |

### Out of scope

| Paper topic | Why |
|---|---|
| Survey of FPGA/ASIC "accelerator" architectures for DNN inference | "Accelerator" = compute hardware |
| Deep learning classification of tumors in radiographs / MRI | Downstream product (patient image); no beam/machine ML |
| ML dose prediction in tissue from CT anatomy, beam model taken as given | Treatment planning, not accelerator physics |
| ML analysis of diffraction patterns / tomograms measured *at* a synchrotron | Downstream product (sample data); the light source is just the tool |
| Jet tagging / Higgs classification on collider detector data | Detector/analysis ML, not accelerator ML |
| Tokamak plasma control (no beam, no accelerator) | Different machine class |
| Beam search in NLP; laser-beam welding; civil-engineering beams | Lexical accidents |

### Borderline — decided case by case (record decisions here)

- **Machine QA of clinical linacs (e.g. patient-specific QA driven by
  delivery-machine logs)**: in scope when the ML input/target is
  machine/beam behavior; out when it is purely dose-in-patient.
- **Detector papers with accelerator-subsystem overlap** (e.g. ML for
  beam-loss monitors that are also machine-protection detectors): in
  scope — machine protection is accelerator operation.
- **Papers with empty abstracts**: never auto-adjudicated on title alone;
  they go to the human pending queue.

## Decision provenance

Every accept/reject carries a `review` record (stage, rule or model +
score, timestamp). Human decisions (`stage: "human"`, `curated: true`)
are terminal: the pipeline never overrides them. Automated accepted /
rejected decisions are also terminal for the pipeline; reversing one is
a human act (edit the record, set `curated: true`).
