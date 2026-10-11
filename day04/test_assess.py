"""Tests for the maturity scoring rules (no model calls)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("assess", Path(__file__).with_name("assess.py"))
assess = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assess)

ALL_AREAS = [a for s in assess.LAYERS.values() for a in s["areas"]]


def answers(default=3, **overrides):
    return {a: {"score": overrides.get(a, default), "note": ""} for a in ALL_AREAS}


def test_layer_scores_its_weakest_area():
    assert assess.layer_scores(answers(5, inventory=1))["Foundation"] == 1


def test_start_at_lowest_structural_layer_below_3():
    # Detection is weak, but Foundation is weaker in structural order: start there.
    a = answers(3, tracing=1, identity=1)
    assert assess.start_layer(assess.layer_scores(a)) == "Foundation"


def test_no_gaps_means_no_start_layer():
    assert assess.start_layer(assess.layer_scores(answers(3))) is None


def test_roadmap_lists_each_gap_in_its_phase():
    lines = assess.roadmap(answers(3, audit=1, playbooks=1))
    assert lines[0] == "Start with: Detection"
    assert any("Days 31-60 · Detection" in line and "audit" in line for line in lines)
    assert any("Days 61-90 · Response" in line and "playbooks" in line for line in lines)
