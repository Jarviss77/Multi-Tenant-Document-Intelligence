import re
from typing import List, Dict

class DocumentProcessor:
    def __init__(self):
        self.section_pattern = re.compile(r'^(#+|\d+\.\s+|\*+\s+)(.+)')

    def chunk_document(self, text: str, chunk_size: int = 500) -> List[Dict]:
        chunks = []

        sections = self._extract_sections(text)

        for section_title, section_content in sections:
            section_chunks = self._split_text_by_semantics(
                section_content,
                chunk_size=chunk_size
            )

            for i, chunk_text in enumerate(section_chunks):
                chunks.append({
                    'section': section_title,
                    'content': chunk_text,
                    'chunk_index': i,
                    'chunk_type': 'document_section',
                    'total_chunks': len(section_chunks)
                })

        return chunks

    def _extract_sections(self, text: str) -> List[tuple]:
        """Extract sections with hierarchy"""
        sections = []
        lines = text.split('\n')

        current_section = "Root"
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line is a section header
            match = self.section_pattern.match(line)
            if match:
                # Save previous section
                if current_content:
                    sections.append((current_section, ' '.join(current_content)))
                    current_content = []

                current_section = match.group(2).strip()
            else:
                current_content.append(line)

        # Add final section
        if current_content:
            sections.append((current_section, ' '.join(current_content)))

        return sections

    def _split_text_by_semantics(self, text: str, chunk_size: int = 500) -> List[str]:
        """Split text into chunks while preserving semantic boundaries"""
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks