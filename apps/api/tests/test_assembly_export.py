def _create_paper_with_outline(client) -> tuple[dict, list[dict]]:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Assembly Harnesses",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert paper_response.status_code == 201
    paper = paper_response.json()
    outline_response = client.post(f"/papers/{paper['id']}/generate-outline", json={})
    assert outline_response.status_code == 200
    return paper, outline_response.json()["outline"]


def _draft_section(client, paper: dict, section: dict, citation_key: str | None = None) -> dict:
    contract_response = client.post(f"/sections/{section['id']}/generate-contract", json={})
    assert contract_response.status_code == 200
    evidence_response = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": section["id"],
            "source_type": "paper_summary",
            "source_ref": f"source-{section['order_index']}",
            "content": f"{section['title']} evidence supports the assembled manuscript.",
            "citation_key": citation_key,
            "confidence": 0.9,
            "metadata": {},
        },
    )
    assert evidence_response.status_code == 201
    evidence = evidence_response.json()
    pack_response = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [evidence["id"]]},
    )
    assert pack_response.status_code == 200
    draft_response = client.post(
        f"/sections/{section['id']}/draft",
        json={"drafting_instructions": f"Draft {section['title']} for assembly."},
    )
    assert draft_response.status_code == 200
    return draft_response.json()["draft"]


def _section(outline: list[dict], title: str) -> dict:
    return next(node for node in outline if node["title"] == title)


def test_assemble_manuscript_from_multiple_sections_in_outline_order(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    introduction = _section(outline, "Introduction")
    framework = _section(outline, "Proposed Framework")
    workflow_components = _section(outline, "Workflow Components")
    implications = _section(outline, "Implications")
    for section in [introduction, framework, workflow_components, implications]:
        _draft_section(client, paper, section, citation_key="smith2024")

    response = client.post(f"/papers/{paper['id']}/assemble", json={})

    assert response.status_code == 200
    payload = response.json()
    manuscript = payload["manuscript"]
    assert payload["paper"]["status"] == "assembly_ready"
    assert manuscript["version"] == 1
    assert manuscript["status"] == "active"
    assert manuscript["included_section_ids"] == [
        introduction["id"],
        framework["id"],
        workflow_components["id"],
        implications["id"],
    ]
    content = manuscript["content"]
    assert content.startswith("# Assembly Harnesses")
    intro_index = content.index("## Introduction")
    framework_index = content.index("## Proposed Framework")
    child_index = content.index("### Workflow Components")
    implications_index = content.index("## Implications")
    assert intro_index < framework_index < child_index < implications_index


def test_assembly_includes_placeholders_for_missing_drafts(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    introduction = _section(outline, "Introduction")
    _draft_section(client, paper, introduction)

    response = client.post(f"/papers/{paper['id']}/assemble", json={})

    assert response.status_code == 200
    manuscript = response.json()["manuscript"]
    assert introduction["id"] in manuscript["included_section_ids"]
    assert manuscript["missing_section_ids"]
    assert "Missing current draft" in manuscript["content"]
    assert any("Conclusion" in warning for warning in manuscript["warnings"])


def test_manuscript_artifact_versioning(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    _draft_section(client, paper, _section(outline, "Introduction"))

    first = client.post(f"/papers/{paper['id']}/assemble", json={})
    second = client.post(f"/papers/{paper['id']}/assemble", json={})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["manuscript"]["version"] == 1
    assert second.json()["manuscript"]["version"] == 2

    versions = client.get(f"/papers/{paper['id']}/manuscripts")
    assert versions.status_code == 200
    payload = versions.json()
    assert [item["version"] for item in payload] == [1, 2]
    assert payload[0]["status"] == "superseded"
    assert payload[1]["status"] == "active"

    current = client.get(f"/papers/{paper['id']}/manuscripts/current")
    assert current.status_code == 200
    assert current.json()["version"] == 2


def test_global_review_persists_manuscript_level_issues(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    introduction = _section(outline, "Introduction")
    _draft_section(client, paper, introduction)
    review_response = client.post(
        f"/sections/{introduction['id']}/review",
        json={"review_instructions": "Leave comments unresolved for global review."},
    )
    assert review_response.status_code == 200
    assemble_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assemble_response.status_code == 200

    review = client.post(
        f"/papers/{paper['id']}/global-review",
        json={"review_instructions": "Check manuscript completeness."},
    )

    assert review.status_code == 200
    payload = review.json()
    assert payload["paper"]["status"] == "final_revision"
    issue_types = {issue["issue_type"] for issue in payload["issues"]}
    assert "missing_section_draft" in issue_types
    assert "unresolved_section_review" in issue_types
    assert "style_issue" in issue_types

    issues = client.get(f"/papers/{paper['id']}/manuscript-issues")
    assert issues.status_code == 200
    assert len(issues.json()) == len(payload["issues"])


def test_markdown_and_latex_export_are_persisted(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    _draft_section(client, paper, _section(outline, "Introduction"), citation_key="smith2024")
    assemble_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assemble_response.status_code == 200
    manuscript = assemble_response.json()["manuscript"]

    markdown_response = client.post(f"/papers/{paper['id']}/export", json={"export_format": "markdown"})
    latex_response = client.post(
        f"/papers/{paper['id']}/export",
        json={
            "export_format": "latex",
            "latex": {
                "author": "Paper Harness",
                "abstract": "A structured harness keeps claims traceable [smith2024].",
                "include_table_of_contents": True,
                "bibliography_file": "references.bib",
                "extra_packages": ["booktabs"],
            },
        },
    )

    assert markdown_response.status_code == 200
    markdown = markdown_response.json()["export"]
    assert markdown["manuscript_id"] == manuscript["id"]
    assert markdown["export_format"] == "markdown"
    assert markdown["content"].startswith("# Assembly Harnesses")
    assert markdown["artifact_path"].endswith(".md")

    assert latex_response.status_code == 200
    latex = latex_response.json()["export"]
    assert latex["export_format"] == "latex"
    assert "\\documentclass{article}" in latex["content"]
    assert "\\usepackage{booktabs}" in latex["content"]
    assert "\\author{Paper Harness}" in latex["content"]
    assert "\\begin{abstract}" in latex["content"]
    assert "\\citep{smith2024}" in latex["content"]
    assert "\\tableofcontents" in latex["content"]
    assert "\\section{Introduction}" in latex["content"]
    assert "\\label{sec:introduction}" in latex["content"]
    assert "\\bibliographystyle{plainnat}" in latex["content"]
    assert "\\bibliography{references}" in latex["content"]
    assert latex["artifact_path"].endswith(".tex")

    exports = client.get(f"/papers/{paper['id']}/exports")
    assert exports.status_code == 200
    assert {item["export_format"] for item in exports.json()} == {"markdown", "latex"}


def test_jcst_template_aware_latex_export_and_compile_validation(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    _draft_section(client, paper, _section(outline, "Introduction"), citation_key="smith2024")
    assemble_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assemble_response.status_code == 200

    response = client.post(
        f"/papers/{paper['id']}/export",
        json={
            "export_format": "latex",
            "latex": {
                "template_name": "jcst",
                "author": "Paper Harness",
                "abstract": "Template-aware export keeps submission structure.",
                "bibliography_file": "references.bib",
                "validate_compile": True,
            },
        },
    )

    assert response.status_code == 200
    export = response.json()["export"]
    assert export["metadata"]["template_name"] == "jcst"
    assert export["metadata"]["compile_validation"]["status"] == "passed"
    assert "JCST template-aware export path" in export["content"]
    assert "\\documentclass[10pt,twocolumn]{article}" in export["content"]
    assert "\\title{ Assembly Harnesses }" in export["content"]
    assert "\\begin{document}" in export["content"]
    assert "\\section{Introduction}" in export["content"]


def test_latex_compile_validation_rejects_unresolved_template_placeholders(client) -> None:
    paper, outline = _create_paper_with_outline(client)
    _draft_section(client, paper, _section(outline, "Introduction"))
    assemble_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assemble_response.status_code == 200

    response = client.post(
        f"/papers/{paper['id']}/export",
        json={
            "export_format": "latex",
            "latex": {
                "template_name": "jcst",
                "template_content": (
                    "\\documentclass{article}\n"
                    "\\begin{document}\n"
                    "{{body}}\n"
                    "{{unknown_placeholder}}\n"
                    "\\end{document}\n"
                ),
                "validate_compile": True,
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["validation"]["status"] == "failed"
    assert "Unresolved template placeholder" in response.json()["detail"]["validation"]["errors"][0]


def test_invalid_assembly_review_and_export_flows(client) -> None:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Invalid Assembly Guards",
            "paper_type": "conceptual",
            "target_language": "English",
        },
    )
    paper = paper_response.json()

    no_outline = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert no_outline.status_code == 400
    assert "outline" in no_outline.json()["detail"]

    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    no_draft = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert no_draft.status_code == 400
    assert "usable current section draft" in no_draft.json()["detail"]

    no_manuscript_review = client.post(f"/papers/{paper['id']}/global-review", json={})
    assert no_manuscript_review.status_code == 400
    assert "current assembled manuscript" in no_manuscript_review.json()["detail"]

    no_manuscript_export = client.post(f"/papers/{paper['id']}/export", json={})
    assert no_manuscript_export.status_code == 400
    assert "current assembled manuscript" in no_manuscript_export.json()["detail"]

    _draft_section(client, paper, _section(outline, "Introduction"))
    locked_only = client.post(f"/papers/{paper['id']}/assemble", json={"include_unlocked": False})
    assert locked_only.status_code == 400
    assert "usable current section draft" in locked_only.json()["detail"]
