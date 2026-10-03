# ADR-007: Multimodal Label Recognition

## Decision
Accept **PDF, PNG, JPEG, WEBP, TIFF**. Pipeline: detect MIME → PDF rasterize → OCR/VLM extract → structured JSON → GraphRAG policy check.  
Store raw + recognized in MinIO. CI uses deterministic text fixtures / mock OCR; profile `vision` for real OCR/VLM.