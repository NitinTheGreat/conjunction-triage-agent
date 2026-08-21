"""Offline tests for the agent, its cache, and the pre-registered decision rule.

Every test here runs with an offline client served from a synthetic cache, so the suite
makes **zero network calls** (constraint 3). No API key is required to run it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.llm import CACHE_VERSION, LLMClient, LLMError, LLMResponse  # noqa: E402
from agent.triage_agent import (  # noqa: E402
    PROMPT_VERSION,
    SCOPE_THRESHOLD,
    AgentVerdict,
    TriageAgent,
    build_evidence_table,
    in_scope,
    parse_verdict,
)

VALID_RESPONSE = json.dumps({
    "predicted_final_risk": -30.0,
    "will_collapse": True,
    "confidence": "high",
    "reasoning": "Both position sigmas shrink steadily and max_risk_scaling falls below 1.",
    "evidence_cited": [
        {"field": "max_risk_scaling", "value": "0.9624"},
        {"field": "target_sigma_max_km", "value": "0.1088"},
    ],
})


@pytest.fixture
def cached_client(tmp_path):
    """An offline client whose cache already holds one response."""
    client = LLMClient(
        provider="anthropic", model="test-model", temperature=0.0,
        prompt_version=PROMPT_VERSION, cache_dir=tmp_path, offline=True,
    )
    return client


def _seed_cache(client: LLMClient, prompt: str, system: str = "", salt: str = "",
                text: str = VALID_RESPONSE, max_tokens: int = 1024) -> str:
    """Seed one cache entry. ``max_tokens`` must match the value the caller will use:
    it is part of the key, so that a raised budget cannot replay a truncated answer."""
    key = client.cache_key(prompt, system, salt, max_tokens)
    client._write_cache(key, LLMResponse(
        text=text, provider=client.provider, model=client.model,
        temperature=client.temperature, prompt_version=client.prompt_version,
        input_tokens=700, output_tokens=180, created_utc="2026-08-19T00:00:00+00:00",
    ))
    return key


# --------------------------------------------------------------------------------------
# the cache
# --------------------------------------------------------------------------------------

class TestCache:
    def test_round_trip(self, cached_client) -> None:
        _seed_cache(cached_client, "prompt A")
        response = cached_client.complete("prompt A")
        assert response.text == VALID_RESPONSE
        assert response.from_cache is True
        assert cached_client.cache_hits == 1
        assert cached_client.calls_made == 0

    def test_offline_miss_raises_rather_than_calling(self, cached_client) -> None:
        with pytest.raises(LLMError, match="cache miss"):
            cached_client.complete("a prompt that was never cached")

    def test_key_depends_on_prompt(self, cached_client) -> None:
        assert cached_client.cache_key("a") != cached_client.cache_key("b")

    def test_key_depends_on_model_and_provider(self, tmp_path) -> None:
        """A different model must not silently reuse another model's answers."""
        a = LLMClient(provider="anthropic", model="m1", cache_dir=tmp_path, offline=True)
        b = LLMClient(provider="anthropic", model="m2", cache_dir=tmp_path, offline=True)
        c = LLMClient(provider="openai", model="m1", cache_dir=tmp_path, offline=True)
        assert a.cache_key("p") != b.cache_key("p")
        assert a.cache_key("p") != c.cache_key("p")

    def test_key_depends_on_prompt_version(self, tmp_path) -> None:
        a = LLMClient(prompt_version="v1", cache_dir=tmp_path, offline=True)
        b = LLMClient(prompt_version="v2", cache_dir=tmp_path, offline=True)
        assert a.cache_key("p") != b.cache_key("p")

    def test_max_tokens_is_part_of_the_key(self, tmp_path) -> None:
        """A raised budget must not replay an answer truncated under a smaller one."""
        client = LLMClient(cache_dir=tmp_path, offline=True)
        assert client.cache_key("p", max_tokens=900) != client.cache_key("p", max_tokens=8000)

    def test_salt_forces_a_distinct_key(self, tmp_path) -> None:
        """Self-consistency needs distinct keys for an identical prompt."""
        client = LLMClient(cache_dir=tmp_path, offline=True)
        assert client.cache_key("p", salt="run-0") != client.cache_key("p", salt="run-1")

    def test_key_is_stable_across_instances(self, tmp_path) -> None:
        a = LLMClient(model="m", cache_dir=tmp_path, offline=True)
        b = LLMClient(model="m", cache_dir=tmp_path, offline=True)
        assert a.cache_key("p", "s") == b.cache_key("p", "s")

    def test_entry_records_audit_fields(self, cached_client, tmp_path) -> None:
        key = _seed_cache(cached_client, "prompt A")
        payload = json.loads((tmp_path / key[:2] / f"{key}.json").read_text(encoding="utf-8"))
        for field in ("provider", "model", "temperature", "prompt_version", "created_utc"):
            assert field in payload

    def test_corrupt_entry_raises(self, cached_client, tmp_path) -> None:
        key = cached_client.cache_key("bad", "", "", 1024)
        path = tmp_path / key[:2]
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{key}.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(LLMError, match="corrupt"):
            cached_client.complete("bad")

    def test_unsupported_provider_raises(self, tmp_path) -> None:
        with pytest.raises(LLMError, match="unsupported provider"):
            LLMClient(provider="nope", cache_dir=tmp_path, offline=True)


# --------------------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------------------

class TestScope:
    def test_threshold_is_the_preregistered_one(self) -> None:
        assert SCOPE_THRESHOLD == -7.0

    def test_in_scope_boundaries(self) -> None:
        assert in_scope(-6.0) is True
        assert in_scope(-7.0) is True      # inclusive
        assert in_scope(-7.0001) is False
        assert in_scope(-30.0) is False

    def test_non_finite_is_out_of_scope(self) -> None:
        assert in_scope(float("nan")) is False


# --------------------------------------------------------------------------------------
# output validation
# --------------------------------------------------------------------------------------

class TestVerdictParsing:
    def test_parses_plain_json(self) -> None:
        verdict = parse_verdict(VALID_RESPONSE)
        assert verdict.will_collapse is True
        assert verdict.confidence == "high"
        assert len(verdict.evidence_cited) == 2

    def test_parses_fenced_json(self) -> None:
        assert parse_verdict(f"Here you go:\n```json\n{VALID_RESPONSE}\n```").will_collapse

    def test_parses_json_with_surrounding_prose(self) -> None:
        assert parse_verdict(f"Analysis follows. {VALID_RESPONSE} Done.").will_collapse

    @pytest.mark.parametrize("bad,reason", [
        ("no json here", "not JSON"),
        ('{"predicted_final_risk": 5.0, "will_collapse": true, "confidence": "high",'
         ' "reasoning": "x", "evidence_cited": []}', "risk above 0"),
        ('{"predicted_final_risk": -99.0, "will_collapse": true, "confidence": "high",'
         ' "reasoning": "x", "evidence_cited": []}', "risk below the floor"),
        ('{"predicted_final_risk": -10.0, "will_collapse": true, "confidence": "certain",'
         ' "reasoning": "x", "evidence_cited": []}', "bad confidence"),
        ('{"predicted_final_risk": -10.0, "will_collapse": true, "confidence": "high",'
         ' "reasoning": "   ", "evidence_cited": []}', "empty reasoning"),
        ('{"will_collapse": true, "confidence": "high", "reasoning": "x",'
         ' "evidence_cited": []}', "missing risk"),
        ('{"predicted_final_risk": -10.0, "will_collapse": true, "confidence": "high",'
         ' "reasoning": "x", "evidence_cited": ["bare string"]}', "malformed citation"),
    ])
    def test_malformed_responses_raise(self, bad, reason) -> None:
        with pytest.raises((LLMError, ValueError)):
            parse_verdict(bad, "test")

    def test_confidence_is_normalised(self) -> None:
        payload = json.loads(VALID_RESPONSE)
        payload["confidence"] = "  HIGH  "
        assert parse_verdict(json.dumps(payload)).confidence == "high"

    def test_floor_value_is_accepted(self) -> None:
        payload = json.loads(VALID_RESPONSE)
        payload["predicted_final_risk"] = -30.0
        assert parse_verdict(json.dumps(payload)).predicted_final_risk == -30.0


# --------------------------------------------------------------------------------------
# evidence rendering
# --------------------------------------------------------------------------------------

def _cdm_frame(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "time_to_tca_days": np.linspace(5.0, 2.1, n),
        "risk_log10": np.linspace(-8.0, -5.0, n),
        "miss_distance_km": np.linspace(0.8, 0.1, n),
        "mahalanobis_distance": np.linspace(3.0, 1.5, n),
        "max_risk_scaling": np.linspace(4.0, 0.9, n),
        "target_sigma_max_km": np.linspace(0.5, 0.1, n),
        "chaser_sigma_max_km": np.linspace(1.9, 0.3, n),
        "relative_speed_kms": np.full(n, 11.0),
        "c_object_type": ["DEBRIS"] * n,
        "target_span_m": np.full(n, 1.0),
        "chaser_span_m": np.full(n, 2.0),
        "F10": np.full(n, 89.0),
        "AP": np.full(n, 6.0),
        "target_obs_used": np.full(n, 400.0),
    })


class TestEvidenceRendering:
    def test_table_has_a_row_per_cdm(self) -> None:
        table = build_evidence_table(_cdm_frame(4))
        # header + separator + 4 rows
        assert len(table.splitlines()) == 6

    def test_rows_are_earliest_first(self) -> None:
        table = build_evidence_table(_cdm_frame(3))
        rows = table.splitlines()[2:]
        times = [float(row.split()[0]) for row in rows]
        assert times == sorted(times, reverse=True)

    def test_empty_frame_raises(self) -> None:
        with pytest.raises(ValueError, match="no CDMs"):
            build_evidence_table(_cdm_frame(0))

    def test_prompt_omits_the_baseline_answer(self, cached_client) -> None:
        """The agent must not be anchored on B1's prediction."""
        agent = TriageAgent(client=cached_client)
        state = agent._node_prepare({
            "series_id": "train:1", "cdms": _cdm_frame(3),
            "features": pd.Series({"latest_risk": -5.0}),
        })
        lowered = state["prompt"].lower()
        assert "baseline" not in lowered
        assert "b1" not in lowered

    def test_missing_column_raises_rather_than_rendering_partial(self, cached_client) -> None:
        agent = TriageAgent(client=cached_client)
        frame = _cdm_frame(3).drop(columns=["max_risk_scaling"])
        with pytest.raises(KeyError, match="max_risk_scaling"):
            agent._node_prepare({
                "series_id": "train:1", "cdms": frame,
                "features": pd.Series({"latest_risk": -5.0}),
            })

    def test_single_cdm_states_no_trend_available(self, cached_client) -> None:
        agent = TriageAgent(client=cached_client)
        state = agent._node_prepare({
            "series_id": "train:1", "cdms": _cdm_frame(1),
            "features": pd.Series({"latest_risk": -5.0}),
        })
        assert "no trend can be computed" in state["prompt"]


# --------------------------------------------------------------------------------------
# the graph, end to end, entirely from cache
# --------------------------------------------------------------------------------------

class TestGraphOffline:
    def test_full_run_from_cache_makes_no_calls(self, cached_client) -> None:
        agent = TriageAgent(client=cached_client)
        cdms = _cdm_frame(3)
        features = pd.Series({"latest_risk": -5.0})
        prepared = agent._node_prepare({
            "series_id": "train:1", "cdms": cdms, "features": features
        })
        from agent.triage_agent import SYSTEM_PROMPT

        _seed_cache(cached_client, prepared["prompt"], system=SYSTEM_PROMPT,
                    max_tokens=agent.max_tokens)

        verdict, meta = agent.analyse("train:1", cdms, features)
        assert verdict.will_collapse is True
        assert meta.from_cache is True
        assert cached_client.calls_made == 0


# --------------------------------------------------------------------------------------
# the pre-registered decision rule
# --------------------------------------------------------------------------------------

class TestDecisionRule:
    """The rule must be mechanical: same statistics in, same outcome out."""

    def _decide(self, median, p, excluded=0):
        import compare_arms

        return compare_arms.decide(median, p, excluded)["outcome"]

    def test_win_requires_both_significance_and_effect_size(self) -> None:
        assert self._decide(-0.20, 0.01) == "AGENT WINS"
        assert self._decide(-0.138, 0.01) == "AGENT WINS"   # boundary is inclusive

    def test_significant_but_small_is_not_a_win(self) -> None:
        assert self._decide(-0.05, 0.01) == "DETECTABLE BUT BELOW THRESHOLD"

    def test_large_effect_without_significance_is_null(self) -> None:
        assert self._decide(-0.50, 0.20) == "NO EFFECT"

    def test_significant_positive_is_a_loss(self) -> None:
        assert self._decide(0.30, 0.01) == "AGENT LOSES"

    def test_non_significant_is_null(self) -> None:
        assert self._decide(-0.10, 0.90) == "NO EFFECT"

    def test_too_many_exclusions_is_uninterpretable(self) -> None:
        """Checked first, ahead of any win claim."""
        assert self._decide(-0.90, 0.001, excluded=6) == "UNINTERPRETABLE"

    def test_exclusions_at_the_limit_still_decide(self) -> None:
        assert self._decide(-0.90, 0.001, excluded=5) == "AGENT WINS"

    def test_minimum_important_difference_matches_the_preregistration(self) -> None:
        import compare_arms

        assert compare_arms.MINIMUM_IMPORTANT_DIFFERENCE == -0.138
        assert compare_arms.N_SPLITS == 50
        assert compare_arms.ALPHA == 0.05


class TestPreregistrationIntegrity:
    def test_file_exists_and_states_the_rule(self) -> None:
        text = (REPO_ROOT / "docs" / "PHASE6_PREREGISTRATION.md").read_text(encoding="utf-8")
        for required in ("AGENT WINS", "NO EFFECT", "UNINTERPRETABLE",
                         "0.138", "Wilcoxon", "50 validation splits"):
            assert required in text, f"pre-registration does not state {required!r}"

    def test_scope_matches_the_preregistration(self) -> None:
        text = (REPO_ROOT / "docs" / "PHASE6_PREREGISTRATION.md").read_text(encoding="utf-8")
        assert "−7.0" in text or "-7.0" in text
        assert SCOPE_THRESHOLD == -7.0
