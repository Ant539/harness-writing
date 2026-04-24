SAMPLE_LATEX = r"""
\documentclass{article}
\begin{document}
\title{Graph Partitioning for Sharded Blockchains}
\noindent {\small\bf Abstract} \quad {\small This paper imports a LaTeX manuscript [smith2024].}
\noindent{\small\bf Keywords} \quad {\small sharding, load balancing, latex import}

\section{Introduction}
Sharded blockchains need careful account placement.

\subsection{Motivation}
Transaction count can hide gas-heavy execution pressure.

\section{Conclusion}
The imported manuscript can now enter the workflow.
\end{document}
"""


def test_import_latex_creates_paper_outline_and_active_drafts(client) -> None:
    response = client.post(
        "/papers/import-latex",
        json={
            "latex_content": SAMPLE_LATEX,
            "source_path": "paper/jsc/JCST-Template-_submit_202105.tex",
            "target_venue": "JCST",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    paper = payload["paper"]
    outline = payload["outline"]
    drafts = payload["drafts"]

    assert paper["title"] == "Graph Partitioning for Sharded Blockchains"
    assert paper["status"] == "outline_ready"
    assert payload["abstract"] == "This paper imports a LaTeX manuscript [smith2024]."
    assert payload["keywords"] == ["sharding", "load balancing", "latex import"]
    assert [node["title"] for node in outline] == ["Introduction", "Motivation", "Conclusion"]
    assert outline[1]["parent_id"] == outline[0]["id"]
    assert len(drafts) == 3
    assert {draft["status"] for draft in drafts} == {"active"}

    assembly_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assembly_response.status_code == 200
    manuscript = assembly_response.json()["manuscript"]
    assert "## Introduction" in manuscript["content"]
    assert "### Motivation" in manuscript["content"]

    export_response = client.post(
        f"/papers/{paper['id']}/export",
        json={
            "export_format": "latex",
            "latex": {
                "abstract": payload["abstract"],
                "bibliography_file": "references.bib",
            },
        },
    )
    assert export_response.status_code == 200
    latex = export_response.json()["export"]["content"]
    assert "\\title{Graph Partitioning for Sharded Blockchains}" in latex
    assert "\\begin{abstract}" in latex
    assert "\\section{Introduction}" in latex
    assert "\\subsection{Motivation}" in latex
    assert "\\bibliography{references}" in latex


def test_import_latex_rejects_manuscripts_without_sections(client) -> None:
    response = client.post(
        "/papers/import-latex",
        json={"latex_content": r"\documentclass{article}\begin{document}No sections.\end{document}"},
    )

    assert response.status_code == 400
    assert "no sections" in response.json()["detail"]
