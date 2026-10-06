"""Tests for `lookup`. They read the real corpus and need no API key."""
import json

import pytest

import tools
from tools import Facts, lookup


def test_finds_a_correct_2025_number():
    r = lookup("Ossbridge", "population_2025")
    assert r["value"] == 52904 and r["unit"] == "residents" and r["source"] == ["NR-01"]
    # the same field written in the other two sentence templates of the profiles
    assert lookup("Ossford", "population_2025")["value"] == 30982          # "Census population: ... in 2025"
    assert lookup("Tarnvale", "population_2025")["value"] == 71388        # "The 2025 census counted ..."


def test_every_field_of_every_district_can_be_read():
    for d in tools.default_facts().districts:
        for f in tools.FIELDS:
            if f == tools.TARIFF_FIELD:
                continue
            r = lookup(d, f)
            assert "error" not in r, (d, f, r)
            assert isinstance(r["value"], (int, float))
    assert len(tools.default_facts().districts) == 12


def test_misspelled_name_gets_a_suggestion_and_is_not_silently_fixed():
    r = lookup("Ossbrige", "area_km2")
    assert "value" not in r
    assert "Ossbridge" in r["error"] and "did you mean" in r["error"]


def test_two_similar_names_are_kept_apart():
    assert lookup("Ossbridge", "area_km2")["value"] == 1284.6
    assert lookup("Ossford", "area_km2")["value"] == 846.2
    assert lookup("ossford", "area_km2")["value"] == 846.2                  # capital letters do not matter
    short = lookup("Oss", "area_km2")                                       # could be either: refuse, name both
    assert "value" not in short
    assert "Ossbridge" in short["error"] and "Ossford" in short["error"]


def test_archived_profile_is_ignored():
    r = lookup("Tarnvale", "population_2025")
    assert r["value"] == 71388 and r["source"] == ["NR-03"]                 # not the 2019 estimate 65,030 of NR-13
    assert "NR-13" in r["note"]
    k = lookup("Kelmarsh", "water_use_2025_megalitres")
    assert k["value"] == 1739 and "NR-14" in k["note"]                      # not 1,652 from the archive
    assert lookup("Ossbridge", "area_km2")["note"] is None                  # no archive, no note


def test_correction_notice_is_applied():
    r = lookup("Brightwater", "area_km2")
    assert r["value"] == 921.4                                              # not the typo 912.4
    assert r["source"] == ["NR-05", "NR-16"] and "912.4" in r["note"]
    assert lookup("Brightwater", "population_2025")["value"] == 44675      # other figures are untouched


def test_unit_is_converted_to_megalitres():
    r = lookup("Lindenmoor", "water_use_2025_megalitres")                  # NR-08 gives 2,151,400 cubic metres
    assert r["value"] == pytest.approx(2151.4) and r["unit"] == "megalitres"
    assert "cubic metres" in r["note"]
    assert lookup("Kelmarsh", "water_use_2025_megalitres")["note"] is not None  # (archive note only)
    assert lookup("Harrowfield", "water_use_2025_megalitres")["value"] == 7146


def test_tariff_and_region():
    r = lookup("region", "water_tariff_2025_tenge_per_m3")
    assert r["value"] == 142.35 and r["source"] == ["NR-15"]                # not the 2024 value 131.80
    assert lookup("Millbrook", "water_tariff_2025_tenge_per_m3")["value"] == 142.35
    assert "error" in lookup("region", "area_km2")                          # 'region' is only for the tariff


def test_bad_arguments_give_errors_not_crashes():
    assert "unknown field" in lookup("Ossbridge", "popluation")["error"]
    assert "must be a string" in lookup(None, "area_km2")["error"]
    assert "must be a string" in lookup("Ossbridge", 5)["error"]
    assert "empty" in lookup("   ", "area_km2")["error"]
    assert "too long" in lookup("x" * 500, "area_km2")["error"]
    assert "error" in lookup("'; DROP TABLE districts; --", "area_km2")     # just a name that does not exist


def test_unknown_water_unit_is_an_error_not_a_guess():
    records = [{"id": "NR-X1", "title": "Testville district profile (2025)",
                "text": "Testville has 5 schools. Households used 120 litres of water during 2025, and more."}]
    r = lookup("Testville", "water_use_2025_megalitres", facts=Facts(records))
    assert "unknown unit" in r["error"] and "litres" in r["error"]


def test_correction_that_does_not_match_is_ignored():
    profile = {"id": "NR-X1", "title": "Testville district profile (2025)",
               "text": "Testville covers 100.0 square kilometres. Founded in 1900."}
    notice = {"id": "NR-X2", "title": "Correction notice - Testville",
              "text": "Correction: the 2025 Testville profile gives the district's area as 999.9 square kilometres. This is a typo. The correct area is 111.1 square kilometres."}
    facts = Facts([profile, notice])
    assert lookup("Testville", "area_km2", facts=facts)["value"] == 100.0
    assert facts.warnings


def test_run_tool_checks_the_arguments_first():
    assert "not valid JSON" in json.loads(tools.run_tool("lookup", "{not json"))["error"]
    assert "JSON object" in json.loads(tools.run_tool("lookup", "[1, 2]"))["error"]
    assert "missing" in json.loads(tools.run_tool("lookup", '{"district": "Ossford"}'))["error"]
    assert "unexpected" in json.loads(tools.run_tool("lookup", '{"district": "Ossford", "field": "area_km2", "x": 1}'))["error"]
    assert "unknown tool" in json.loads(tools.run_tool("delete_everything", "{}"))["error"]
    ok = json.loads(tools.run_tool("lookup", '{"district": "Ossford", "field": "area_km2"}'))
    assert ok["value"] == 846.2
