"""Import an existing LaTeX manuscript into section-centric workflow artifacts."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from app.models import DraftUnit, OutlineNode, Paper, SourceMaterial
from app.models.enums import ArtifactStatus, DraftKind, EvidenceSourceType, PaperStatus, SectionStatus
from app.schemas.latex_import import LatexImportRequest


@dataclass(frozen=True)
class ParsedLatexSection:
    title: str
    level: int
    content: str


@dataclass(frozen=True)
class ParsedLatexManuscript:
    title: str
    abstract: str | None
    keywords: list[str]
    sections: list[ParsedLatexSection]


class LatexManuscriptImporter:
    """Creates paper, outline, and active draft artifacts from a LaTeX manuscript."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def import_manuscript(
        self,
        request: LatexImportRequest,
    ) -> tuple[Paper, SourceMaterial, list[OutlineNode], list[DraftUnit], ParsedLatexManuscript]:
        parsed = self.parse(request.latex_content)
        if not parsed.sections:
            raise HTTPException(status_code=400, detail="LaTeX manuscript contains no sections.")

        paper = Paper(
            title=parsed.title,
            paper_type=request.paper_type,
            target_language=request.target_language,
            target_venue=request.target_venue,
            status=PaperStatus.OUTLINE_READY,
            global_style_guide={
                "latex_import": {
                    "source_path": request.source_path,
                    "abstract": parsed.abstract,
                    "keywords": parsed.keywords,
                }
            },
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)

        source = SourceMaterial(
            paper_id=paper.id,
            source_type=EvidenceSourceType.NOTE,
            title="Imported LaTeX manuscript",
            source_ref=request.source_path,
            content=request.latex_content,
            metadata_json={
                "abstract": parsed.abstract,
                "keywords": parsed.keywords,
                "import_format": "latex",
            },
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)

        sections, drafts = self._persist_sections(paper, parsed.sections)
        return paper, source, sections, drafts, parsed

    def parse(self, content: str) -> ParsedLatexManuscript:
        document_body = self._document_body(content)
        title = self._clean_inline(
            self._command_argument(document_body, "title") or "Imported LaTeX Paper"
        )
        abstract = self._extract_abstract(content)
        keywords = self._extract_keywords(content)
        sections = self._extract_sections(document_body)
        return ParsedLatexManuscript(
            title=title,
            abstract=abstract,
            keywords=keywords,
            sections=sections,
        )

    def _persist_sections(
        self,
        paper: Paper,
        parsed_sections: list[ParsedLatexSection],
    ) -> tuple[list[OutlineNode], list[DraftUnit]]:
        nodes: list[OutlineNode] = []
        drafts: list[DraftUnit] = []
        parent_stack: dict[int, uuid.UUID] = {}
        sibling_counts: dict[uuid.UUID | None, int] = {}

        for parsed in parsed_sections:
            parent_id = self._parent_for(parsed.level, parent_stack)
            order_index = sibling_counts.get(parent_id, 0) + 1
            sibling_counts[parent_id] = order_index
            node = OutlineNode(
                paper_id=paper.id,
                parent_id=parent_id,
                title=parsed.title,
                level=parsed.level,
                goal=f"Imported LaTeX section: {parsed.title}",
                word_budget=self._word_budget(parsed.content),
                status=SectionStatus.DRAFTED,
                order_index=order_index,
                metadata_json={"imported_from_latex": True},
            )
            self.session.add(node)
            self.session.commit()
            self.session.refresh(node)
            nodes.append(node)
            parent_stack[parsed.level] = node.id
            for deeper_level in list(parent_stack):
                if deeper_level > parsed.level:
                    parent_stack.pop(deeper_level)

            draft = DraftUnit(
                section_id=node.id,
                kind=DraftKind.SECTION_DRAFT,
                version=1,
                content=parsed.content.strip(),
                supported_evidence_ids=[],
                status=ArtifactStatus.ACTIVE,
            )
            self.session.add(draft)
            self.session.commit()
            self.session.refresh(draft)
            drafts.append(draft)

        return nodes, drafts

    def _parent_for(self, level: int, parent_stack: dict[int, uuid.UUID]) -> uuid.UUID | None:
        for candidate_level in range(level - 1, 0, -1):
            if candidate_level in parent_stack:
                return parent_stack[candidate_level]
        return None

    def _word_budget(self, content: str) -> int | None:
        words = re.findall(r"\b[\w-]+\b", self._strip_latex_commands(content))
        return max(150, len(words)) if words else None

    def _extract_sections(self, content: str) -> list[ParsedLatexSection]:
        body = content
        heading_pattern = re.compile(
            r"\\(?P<command>section|subsection|subsubsection)\*?\{(?P<title>[^{}]+)\}"
        )
        matches = list(heading_pattern.finditer(body))
        sections: list[ParsedLatexSection] = []
        levels = {"section": 1, "subsection": 2, "subsubsection": 3}
        for index, match in enumerate(matches):
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            raw_content = body[match.end() : next_start].strip()
            title = self._clean_inline(match.group("title"))
            sections.append(
                ParsedLatexSection(
                    title=title,
                    level=levels[match.group("command")],
                    content=raw_content,
                )
            )
        return sections

    def _extract_abstract(self, content: str) -> str | None:
        environment = re.search(
            r"\\begin\{abstract\}(?P<abstract>.*?)\\end\{abstract\}",
            content,
            flags=re.DOTALL,
        )
        if environment:
            return self._clean_block(environment.group("abstract"))

        jcst = re.search(
            r"\\noindent\s*\{\\small\\bf\s+Abstract\}\s*\\quad\s*\{\\small\s+(?P<abstract>.*?)\}",
            content,
            flags=re.DOTALL,
        )
        if jcst:
            return self._clean_block(jcst.group("abstract"))
        return None

    def _extract_keywords(self, content: str) -> list[str]:
        match = re.search(
            r"\\noindent\s*\{\\small\\bf\s+Keywords\}\s*\\quad\s*\{\\small\s+(?P<keywords>.*?)\}",
            content,
            flags=re.DOTALL,
        )
        if not match:
            return []
        return [
            keyword.strip()
            for keyword in self._clean_block(match.group("keywords")).split(",")
            if keyword.strip()
        ]

    def _document_body(self, content: str) -> str:
        begin = content.find(r"\begin{document}")
        if begin >= 0:
            content = content[begin + len(r"\begin{document}") :]
        end = content.find(r"\end{document}")
        if end >= 0:
            content = content[:end]
        bibliography = content.find(r"\begin{thebibliography}")
        if bibliography >= 0:
            content = content[:bibliography]
        return self._remove_comments(content)

    def _command_argument(self, content: str, command: str) -> str | None:
        marker = f"\\{command}"
        index = content.find(marker)
        if index < 0:
            return None
        brace_start = content.find("{", index + len(marker))
        if brace_start < 0:
            return None
        depth = 0
        for position in range(brace_start, len(content)):
            char = content[position]
            if char == "{" and not self._escaped(content, position):
                depth += 1
            elif char == "}" and not self._escaped(content, position):
                depth -= 1
                if depth == 0:
                    return content[brace_start + 1 : position]
        return None

    def _remove_comments(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            lines.append(re.sub(r"(?<!\\)%.*$", "", line))
        return "\n".join(lines)

    def _clean_block(self, text: str) -> str:
        return " ".join(self._strip_latex_commands(text).split())

    def _clean_inline(self, text: str) -> str:
        return self._clean_block(text).strip()

    def _strip_latex_commands(self, text: str) -> str:
        without_commands = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", text)
        without_math = without_commands.replace("$", " ")
        return re.sub(r"[{}]", " ", without_math)

    def _escaped(self, content: str, position: int) -> bool:
        backslashes = 0
        index = position - 1
        while index >= 0 and content[index] == "\\":
            backslashes += 1
            index -= 1
        return backslashes % 2 == 1
