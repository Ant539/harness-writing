from app.services.evaluation import AcademicEvalCase, AcademicPaperEvaluator


def test_academic_evaluator_rewards_method_result_and_story_coverage() -> None:
    case = AcademicEvalCase.from_mapping(
        {
            "title": "Adaptive Scheduling for Edge Clusters",
            "field": "Computer systems",
            "target_venue": "Top-tier systems conference",
            "audience": "Distributed systems researchers",
            "method_summary": (
                "We implemented an adaptive scheduler for edge clusters and evaluated latency, "
                "throughput, and straggler mitigation on a 32-node testbed."
            ),
            "result_summary": (
                "The scheduler reduced tail latency by 38 percent and improved throughput by "
                "21 percent under bursty workloads."
            ),
            "expected_contributions": [
                "An adaptive scheduling mechanism for bursty edge workloads.",
                "An empirical evaluation showing lower tail latency and higher throughput.",
            ],
            "required_facts": [
                "32-node testbed",
                "38 percent tail latency",
                "21 percent throughput",
            ],
            "forbidden_claims": ["global optimal scheduling"],
        }
    )
    manuscript = """
# Abstract

We present an adaptive scheduling mechanism for bursty edge workloads. The system was
implemented for edge clusters and evaluated on a 32-node testbed. It reduced tail latency
by 38 percent and improved throughput by 21 percent under bursty workloads.

# Introduction

Edge clusters face a challenge: bursty workloads create stragglers that make latency hard
to control. We propose an adaptive scheduler and demonstrate its contribution through an
empirical evaluation.

# Method

The method implements an adaptive scheduler for edge clusters and measures latency,
throughput, and straggler mitigation on the 32-node testbed.

# Results

The results show a 38 percent reduction in tail latency and a 21 percent throughput
improvement under bursty workloads.

# Discussion

The finding suggests that adaptive scheduling can improve performance, but the scope is
limited to the evaluated testbed and workload mix. Threats to validity include workload
representativeness.

# Conclusion

The paper contributes an adaptive scheduling approach and evidence that it improves tail
latency and throughput for bursty edge workloads.
"""

    evaluation = AcademicPaperEvaluator().evaluate(case, manuscript)

    assert evaluation.overall_score >= 75
    assert evaluation.readiness in {"strong", "near_submission_ready"}
    assert not evaluation.blocking_issues
    assert evaluation.metadata["missing_sections"] == []


def test_academic_evaluator_blocks_missing_results_and_forbidden_claims() -> None:
    case = AcademicEvalCase.from_mapping(
        {
            "title": "Adaptive Scheduling for Edge Clusters",
            "method_summary": "We evaluated an adaptive scheduler on a 32-node testbed.",
            "result_summary": "The scheduler reduced tail latency by 38 percent.",
            "expected_contributions": ["Adaptive scheduling for bursty edge workloads."],
            "required_facts": ["38 percent tail latency"],
            "forbidden_claims": ["global optimal scheduling"],
        }
    )
    manuscript = """
# Abstract

This paper introduces global optimal scheduling for all edge workloads.

# Introduction

The method is important and revolutionary.
"""

    evaluation = AcademicPaperEvaluator().evaluate(case, manuscript)

    assert evaluation.readiness == "blocked"
    assert evaluation.overall_score <= 50
    assert evaluation.forbidden_claim_hits == ["global optimal scheduling"]
    assert "38 percent tail latency" in evaluation.missing_required_facts
