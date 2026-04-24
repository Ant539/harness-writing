"""Deterministic export generation for Milestone 5.

TODO(real-export): add template-aware exporters and bibliography-aware rendering
behind the same ExportArtifact persistence contract.
"""

import re
from pathlib import Path

from app.models import AssembledManuscript, Paper
from app.models.enums import ExportFormat
from app.schemas.assembly import LatexExportOptions


class ExportGenerator:
    """Creates reproducible export text from an assembled manuscript."""

    def generate(
        self,
        *,
        paper: Paper,
        manuscript: AssembledManuscript,
        export_format: ExportFormat,
        latex_options: LatexExportOptions | None = None,
    ) -> str:
        if export_format == ExportFormat.MARKDOWN:
            return manuscript.content
        if export_format == ExportFormat.LATEX:
            return self._latex(paper, manuscript, latex_options or LatexExportOptions())
        raise ValueError(f"Unsupported export format: {export_format}")

    def extension_for(self, export_format: ExportFormat) -> str:
        return "tex" if export_format == ExportFormat.LATEX else "md"

    def write_file(self, *, content: str, artifact_path: str) -> None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _latex(
        self,
        paper: Paper,
        manuscript: AssembledManuscript,
        options: LatexExportOptions,
    ) -> str:
        abstract, content_lines = self._extract_abstract(manuscript.content, options.abstract)
        body_lines: list[str] = []
        labels: set[str] = set()

        for line in content_lines:
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                body_lines.append(self._heading("section", line[3:], labels))
                continue
            if line.startswith("### "):
                body_lines.append(self._heading("subsection", line[4:], labels))
                continue
            if line.startswith("#### "):
                body_lines.append(self._heading("subsubsection", line[5:], labels))
                continue
            if line.startswith("##### "):
                body_lines.append(self._heading("paragraph", line[6:], labels))
                continue
            body_lines.append(self._inline_latex(line, options.citation_command))

        body = "\n".join(body_lines).strip()
        bibliography = self._bibliography(options)
        if options.template_content or self._template_name(options) == "jcst":
            return self._template_latex(
                paper=paper,
                options=options,
                abstract=abstract,
                body=body,
                bibliography=bibliography,
            )
        return (
            f"\\documentclass{{{self._safe_class(options.document_class)}}}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{lmodern}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage{natbib}\n"
            "\\usepackage{hyperref}\n"
            f"{self._extra_packages(options)}"
            f"\\title{{{self._escape(paper.title)}}}\n"
            f"{self._author(options)}"
            "\\date{}\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            f"{self._abstract(abstract)}"
            f"{self._table_of_contents(options)}"
            f"{body}\n\n"
            f"{bibliography}"
            "\\end{document}\n"
        )

    def validate_latex_compile(self, content: str) -> dict:
        """Run a deterministic LaTeX compile preflight without shelling out."""

        errors: list[str] = []
        warnings: list[str] = []
        if "\\begin{document}" not in content:
            errors.append("Missing \\begin{document}.")
        if "\\end{document}" not in content:
            errors.append("Missing \\end{document}.")
        if "{{" in content or "}}" in content:
            errors.append("Unresolved template placeholder remains in exported LaTeX.")
        if self._unescaped_count(content, "{") != self._unescaped_count(content, "}"):
            errors.append("Unbalanced LaTeX braces detected.")

        begin_envs = re.findall(r"\\begin\{([^{}]+)\}", content)
        end_envs = re.findall(r"\\end\{([^{}]+)\}", content)
        if begin_envs.count("document") != 1 or end_envs.count("document") != 1:
            errors.append("Expected exactly one document environment.")
        for env in sorted(set(begin_envs) | set(end_envs)):
            if begin_envs.count(env) != end_envs.count(env):
                errors.append(f"Environment '{env}' has unmatched begin/end commands.")
        if "\\bibliography{" in content and "\\bibliographystyle{" not in content:
            warnings.append("Bibliography file is configured without an explicit bibliography style.")

        return {
            "status": "passed" if not errors else "failed",
            "errors": errors,
            "warnings": warnings,
        }

    def _extract_abstract(
        self,
        content: str,
        configured_abstract: str | None,
    ) -> tuple[str | None, list[str]]:
        if configured_abstract:
            return configured_abstract.strip(), content.splitlines()

        lines = content.splitlines()
        abstract_start = None
        for index, line in enumerate(lines):
            if line.strip().lower() == "## abstract":
                abstract_start = index
                break
        if abstract_start is None:
            return None, lines

        abstract_lines: list[str] = []
        body_lines: list[str] = []
        index = 0
        while index < len(lines):
            if index != abstract_start:
                body_lines.append(lines[index])
                index += 1
                continue
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                if lines[index].strip():
                    abstract_lines.append(lines[index].strip())
                index += 1
        abstract = " ".join(abstract_lines).strip() or None
        return abstract, body_lines

    def _heading(self, command: str, title: str, labels: set[str]) -> str:
        label = self._unique_label(title, labels)
        return f"\\{command}{{{self._escape(title)}}}\\label{{{label}}}"

    def _unique_label(self, title: str, labels: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
        candidate = f"sec:{base}"
        suffix = 2
        while candidate in labels:
            candidate = f"sec:{base}-{suffix}"
            suffix += 1
        labels.add(candidate)
        return candidate

    def _inline_latex(self, text: str, citation_command: str) -> str:
        protected: dict[str, str] = {}

        def protect(match: re.Match[str]) -> str:
            keys = re.sub(r"\s*[,;]\s*", ",", match.group(1).strip())
            token = f"@@LATEXTOKEN{len(protected)}@@"
            protected[token] = f"\\{self._safe_citation_command(citation_command)}{{{keys}}}"
            return token

        citation_pattern = re.compile(
            r"\[([A-Za-z][A-Za-z0-9_:-]*(?:\s*[,;]\s*[A-Za-z][A-Za-z0-9_:-]*)*)\]"
        )
        with_tokens = citation_pattern.sub(protect, text)
        escaped = self._escape(with_tokens)
        escaped = re.sub(r"\\_(.+?)\\_", r"\\emph{\1}", escaped)
        for token, replacement in protected.items():
            escaped = escaped.replace(token, replacement)
        return escaped

    def _abstract(self, abstract: str | None) -> str:
        if not abstract:
            return ""
        return (
            "\\begin{abstract}\n"
            f"{self._inline_latex(abstract, 'citep')}\n"
            "\\end{abstract}\n\n"
        )

    def _template_latex(
        self,
        *,
        paper: Paper,
        options: LatexExportOptions,
        abstract: str | None,
        body: str,
        bibliography: str,
    ) -> str:
        template = options.template_content or self._builtin_template(self._template_name(options))
        replacements = {
            "document_class": self._safe_class(options.document_class),
            "packages": self._default_packages() + self._extra_packages(options),
            "extra_packages": self._extra_packages(options),
            "title": self._escape(paper.title),
            "author": self._author(options).strip(),
            "abstract": self._abstract(abstract).strip(),
            "body": body,
            "bibliography": bibliography.strip(),
        }
        rendered = template
        for key, value in replacements.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
            rendered = rendered.replace(f"{{{{ {key} }}}}", value)
        return rendered.strip() + "\n"

    def _builtin_template(self, template_name: str | None) -> str:
        if template_name == "jcst":
            return (
                "\\documentclass[10pt,twocolumn]{article}\n"
                "% JCST template-aware export path. Replace with the official class file "
                "when available.\n"
                "{{packages}}"
                "\\title{ {{title}} }\n"
                "{{author}}\n"
                "\\date{}\n"
                "\\begin{document}\n"
                "\\maketitle\n\n"
                "{{abstract}}\n\n"
                "{{body}}\n\n"
                "{{bibliography}}\n"
                "\\end{document}\n"
            )
        raise ValueError(f"Unsupported LaTeX template: {template_name}")

    def _template_name(self, options: LatexExportOptions) -> str | None:
        if not options.template_name:
            return None
        return re.sub(r"[^A-Za-z0-9_-]", "", options.template_name).lower() or None

    def _default_packages(self) -> str:
        return (
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{lmodern}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage{natbib}\n"
            "\\usepackage{hyperref}\n"
        )

    def _author(self, options: LatexExportOptions) -> str:
        if not options.author:
            return ""
        return f"\\author{{{self._escape(options.author)}}}\n"

    def _table_of_contents(self, options: LatexExportOptions) -> str:
        return "\\tableofcontents\n\\newpage\n\n" if options.include_table_of_contents else ""

    def _bibliography(self, options: LatexExportOptions) -> str:
        if not options.bibliography_file:
            return ""
        style = options.bibliography_style or "plainnat"
        return (
            f"\\bibliographystyle{{{self._safe_class(style)}}}\n"
            f"\\bibliography{{{self._safe_bibliography_file(options.bibliography_file)}}}\n\n"
        )

    def _extra_packages(self, options: LatexExportOptions) -> str:
        lines = []
        for package in options.extra_packages:
            package_name = self._safe_package(package)
            if package_name:
                lines.append(f"\\usepackage{{{package_name}}}\n")
        return "".join(lines)

    def _unescaped_count(self, text: str, char: str) -> int:
        return len(re.findall(rf"(?<!\\){re.escape(char)}", text))

    def _safe_class(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]", "", value)
        return safe or "article"

    def _safe_package(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", value)

    def _safe_citation_command(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z]", "", value)
        return safe or "citep"

    def _safe_bibliography_file(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_./:-]", "", value)
        return safe.removesuffix(".bib") or "references"

    def _escape(self, text: str) -> str:
        escaped = text
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
        }
        for source, replacement in replacements.items():
            escaped = escaped.replace(source, replacement)
        return escaped
