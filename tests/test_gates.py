"""Tests for Stage B deterministic gates."""

import pytest

from living_review.gates import ACCEPT, GRAY, REJECT, apply_gates, venue_is_whitelisted


class TestAutoAccept:
    def test_acc_ph_primary_category(self, make_paper):
        p = make_paper(arxiv_categories=["physics.acc-ph", "cs.LG"])
        r = apply_gates(p)
        assert r.decision == ACCEPT
        assert r.rule == "auto_accept:acc-ph"

    def test_acc_ph_secondary_does_not_auto_accept(self, make_paper):
        p = make_paper(arxiv_categories=["cs.LG", "physics.acc-ph"], venue="arXiv")
        assert apply_gates(p).decision == GRAY

    def test_prab_venue_with_ml_keyword(self, make_paper):
        p = make_paper(
            venue="Physical Review Accelerators and Beams",
            abstract="We apply deep learning to orbit correction.",
        )
        r = apply_gates(p)
        assert r.decision == ACCEPT
        assert r.rule == "auto_accept:venue_whitelist"

    def test_jacow_conference_venues(self, make_paper):
        for venue in ("Proc. IPAC'23", "ICALEPCS 2023", "Proceedings of NAPAC", "IBIC 2022"):
            p = make_paper(venue=venue, abstract="A neural network surrogate model.")
            assert apply_gates(p).decision == ACCEPT, venue

    def test_whitelist_venue_without_ml_stays_gray(self, make_paper):
        p = make_paper(
            venue="Proc. IPAC'23",
            abstract="Mechanical design of a new vacuum chamber.",
        )
        assert apply_gates(p).decision == GRAY


class TestAutoRejectHardware:
    def test_dnn_hardware_accelerator_survey(self, make_paper):
        p = make_paper(
            title="A Survey of Accelerator Architectures for Deep Neural Networks",
            abstract="We review FPGA and ASIC accelerator designs for efficient "
            "DNN inference, comparing throughput and energy efficiency of "
            "systolic arrays and in-memory computing chips.",
            venue="ACM Computing Surveys",
        )
        r = apply_gates(p)
        assert r.decision == REJECT
        assert r.rule == "auto_reject:hw_accelerator_context"

    def test_dram_gnn_accelerator(self, make_paper):
        p = make_paper(
            title="STING: A Stochastic In-DRAM Accelerator for Graph Neural Networks",
            abstract="A DRAM-based compute-in-memory accelerator achieving high "
            "throughput and low-power GNN inference on edge devices.",
        )
        assert apply_gates(p).decision == REJECT

    def test_hardware_paper_mentioning_beam_is_not_rejected(self, make_paper):
        # Conjunction rule: any accelerator-system vocabulary blocks rejection.
        p = make_paper(
            title="An FPGA accelerator for real-time beam position monitor processing",
            abstract="We present an FPGA design for BPM signal processing at a synchrotron.",
        )
        assert apply_gates(p).decision == GRAY


class TestAutoRejectForeignDomain:
    def test_customer_churn(self, make_paper):
        p = make_paper(
            title="Machine Learning to Reduce Customer Churn in the Promotional Products Industry",
            abstract="We predict customer churn for marketing campaigns using gradient boosting.",
        )
        r = apply_gates(p)
        assert r.decision == REJECT
        assert r.rule == "auto_reject:foreign_domain"

    def test_medical_imaging_without_accelerator_context(self, make_paper):
        p = make_paper(
            title="Deep Learning Framework for X-ray-based Classification of Rotator Cuff Tears",
            abstract="A dual-stage attention network classifies shoulder radiographs of patients.",
        )
        assert apply_gates(p).decision == REJECT

    def test_education_paper(self, make_paper):
        p = make_paper(
            title="Impact of Problem-Based Learning on Physics Students",
            abstract="A study of learning outcomes among undergraduate students in classrooms.",
        )
        assert apply_gates(p).decision == REJECT

    def test_tokamak_paper(self, make_paper):
        p = make_paper(
            title="Plasma Surrogate Modelling using Fourier Neural Operators",
            abstract="We emulate plasma evolution in tokamaks for fusion control.",
        )
        assert apply_gates(p).decision == REJECT

    def test_civil_beams_not_auto_rejected_goes_gray(self, make_paper):
        # "beams" hits accelerator vocabulary, so the conjunction fails —
        # deliberately conservative; the NLI adjudicator handles it.
        p = make_paper(
            title="ANN prediction of fire resistance of FRP-strengthened beams",
            abstract="Concrete beams strengthened with FRP are modelled with neural networks.",
        )
        assert apply_gates(p).decision == GRAY


class TestMedicalAcceleratorMustNotReject:
    """Regression: medical accelerator papers are IN scope (SCOPE.md)."""

    def test_proton_therapy_pencil_beam(self, make_paper):
        p = make_paper(
            title="Machine learning prediction of pencil beam scanning spot positions",
            abstract="We train a model on proton therapy delivery log files to predict "
            "spot positions of the pencil beam at the gantry for patient-specific QA.",
            venue="Medical Physics",
        )
        assert apply_gates(p).decision == GRAY

    def test_medical_linac_qa(self, make_paper):
        p = make_paper(
            title="Anomaly detection for medical linac performance drift",
            abstract="Daily QA data of a clinical linac is monitored with an autoencoder "
            "to detect dosimetric drift before patient treatments.",
            venue="Physics in Medicine and Biology",
        )
        assert apply_gates(p).decision == GRAY


class TestDetectorContext:
    """Regression from the 2026-07 model benchmark: detector-analysis ML
    (NLI scores 0.92-0.99) must route to pending, not to the adjudicator."""

    def test_track_reconstruction_paper_routes_to_pending(self, make_paper):
        p = make_paper(
            title="Combined track finding with GNN & CKF",
            abstract="Graph neural networks for track reconstruction on silicon "
            "detector hits at the LHC, combined with a combinatorial Kalman filter.",
        )
        r = apply_gates(p)
        assert r.decision == GRAY
        assert r.rule == "detector_context"

    def test_particle_identification_paper(self, make_paper):
        p = make_paper(
            title="Particle identification in the GlueX detector with machine learning",
            abstract="We train classifiers on calorimeter and tracking detector data "
            "for particle identification in physics analysis at GlueX.",
        )
        assert apply_gates(p).rule == "detector_context"

    def test_machine_protection_crossover_not_caught(self, make_paper):
        # Papers with genuine machine-subsystem content stay in the normal
        # gray zone even if they mention detectors.
        p = make_paper(
            title="ML for beam loss monitor triggers in machine protection",
            abstract="We use detector data from beam loss monitors for machine "
            "protection and beam diagnostics at the synchrotron.",
        )
        r = apply_gates(p)
        assert r.rule != "detector_context"


class TestGrayZone:
    def test_empty_abstract_routes_to_pending_rule(self, make_paper):
        p = make_paper(abstract="", venue="Some Journal")
        r = apply_gates(p)
        assert r.decision == GRAY
        assert r.rule == "empty_abstract"

    def test_genuine_accel_ml_paper_in_ml_venue_is_gray(self, make_paper):
        p = make_paper(
            title="Reinforcement learning for online tuning of the LCLS beamline",
            abstract="We maximize FEL pulse energy with RL on the linac at SLAC.",
            venue="NeurIPS ML4Phys Workshop",
        )
        assert apply_gates(p).decision == GRAY


class TestVenueWhitelist:
    def test_variants(self):
        assert venue_is_whitelisted("Phys. Rev. Accel. Beams")
        assert venue_is_whitelisted("Physical Review Special Topics - Accelerators and Beams")
        assert venue_is_whitelisted("Nuclear Instruments and Methods in Physics Research Section A")
        assert venue_is_whitelisted("JACoW IPAC 2024")
        assert not venue_is_whitelisted("Nature Medicine")
        assert not venue_is_whitelisted(None)
