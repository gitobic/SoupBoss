# resumes - Test Resume Collection

Sample resumes for testing SoupBoss matching algorithms. Downloaded from various sources online.

## File Types
- **PDF and DOCX pairs** - Same resume in multiple formats for testing parsers
- **TXT** - Plain text version for baseline testing
- **Various roles** - Accountant, Desktop Support, Office Coordinator

## Files
- `01-*/02-*` - Numbered variants of same role types
- `Mickey01_docx.docx` - Disney-themed test resume
- `Minnie01_docx.docx` - Another Disney test case
- `sample_resume.txt` - Basic text resume for parser testing

## Usage
```bash
# Add individual resume
uv run python main.py resumes add ref_data/resumes/01-Accountant.pdf --name "Accountant Sample"

# Add all resumes in directory
find ref_data/resumes -name "*.pdf" -exec uv run python main.py resumes add {} \;
```

## Notes
- Use these for testing embedding generation and matching quality
- Good mix of technical and non-technical roles
- PDF/DOCX pairs help validate text extraction consistency