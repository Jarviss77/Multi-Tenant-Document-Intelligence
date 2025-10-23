from typing import List, Dict
import re


class TranscriptProcessor:
    def __init__(self):
        self.speaker_pattern = re.compile(r'^(?:\[?(\w+)\]?:\s*)(.+)')

    def preprocess_transcript(self, text: str) -> List[Dict]:
        """Split transcript into meaningful chunks with metadata"""
        chunks = []
        lines = text.split('\n')

        current_speaker = None
        current_chunk = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract speaker and content
            match = self.speaker_pattern.match(line)
            if match:
                # Save previous chunk
                if current_chunk:
                    chunks.append({
                        'speaker': current_speaker,
                        'content': ' '.join(current_chunk),
                        'chunk_type': 'dialogue'
                    })
                    current_chunk = []

                current_speaker = match.group(1)
                content = match.group(2)
            else:
                content = line

            # Split long content into smaller chunks
            sentences = re.split(r'[.!?]+', content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 10:  # Meaningful sentence
                    current_chunk.append(sentence)

                    # Create chunk if it reaches optimal size
                    if len(' '.join(current_chunk)) > 200:
                        chunks.append({
                            'speaker': current_speaker,
                            'content': ' '.join(current_chunk),
                            'chunk_type': 'dialogue'
                        })
                        current_chunk = []

        # Add final chunk
        if current_chunk:
            chunks.append({
                'speaker': current_speaker,
                'content': ' '.join(current_chunk),
                'chunk_type': 'dialogue'
            })

        return chunks

    def extract_key_segments(self, chunks: List[Dict]) -> List[Dict]:
        """Extract important segments based on content"""
        important_segments = []

        for chunk in chunks:
            content = chunk['content'].lower()

            # Identify important segments (customize based on your domain)
            important_keywords = [
                'action item', 'decision', 'summary', 'conclusion',
                'important', 'critical', 'key point', 'next step'
            ]

            if any(keyword in content for keyword in important_keywords):
                chunk['segment_type'] = 'important'
                important_segments.append(chunk)

        return important_segments