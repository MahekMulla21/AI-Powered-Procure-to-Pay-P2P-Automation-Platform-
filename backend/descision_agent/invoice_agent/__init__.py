"""
invoice_agent package
=====================
Self-contained invoice extraction module for the decision pipeline.
Uses the same Invoice_* folders (config, ocr, processing, llm)
as the main invoice pipeline but does NOT write to the database.

Purpose: extract invoice fields purely for cross-reference checking
by the decision agent (PO / PR / MSA / SOW validation).
"""
