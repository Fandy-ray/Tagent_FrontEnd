#!/usr/bin/env python3
"""Convert PDF pages to Markdown with an OpenAI-compatible vision model."""

import argparse
import base64
import logging
import os
import sys
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from pdf2image import convert_from_path, pdfinfo_from_path
from tqdm import tqdm


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def encode_image_to_base64(image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def create_client(api_key: str | None, base_url: str, auth_mode: str) -> OpenAI:
    if auth_mode == "bearer" and not api_key:
        raise ValueError("An API key is required when auth mode is bearer")
    return OpenAI(api_key=api_key or "not-needed", base_url=base_url.rstrip("/"))


def call_vision_model(client: OpenAI, encoded_image: str, model_name: str) -> str:
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract all content from the textbook page as Markdown. Preserve headings, "
                    "tables, and structure. Use LaTeX for formulas and describe diagrams or charts "
                    "precisely. Return only the extracted content."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Parse this textbook page."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        },
                    },
                ],
            },
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content or ""


def pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    *,
    dpi: int,
    poppler_path: str | None,
    api_key: str | None,
    base_url: str,
    model_name: str,
    auth_mode: str,
) -> Path:
    source = Path(pdf_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {source}")

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    image_directory = destination / "pages"
    image_directory.mkdir(parents=True, exist_ok=True)
    markdown_path = destination / f"{source.stem}.md"
    markdown_path.write_text("", encoding="utf-8")

    client = create_client(api_key, base_url, auth_mode)
    page_count = int(pdfinfo_from_path(source, poppler_path=poppler_path)["Pages"])
    logger.info("Processing %s pages from %s", page_count, source)

    with tqdm(total=page_count, desc="PDF vision parsing", unit="page") as progress:
        for page_number in range(1, page_count + 1):
            images = convert_from_path(
                source,
                first_page=page_number,
                last_page=page_number,
                dpi=dpi,
                poppler_path=poppler_path,
            )
            if not images:
                raise RuntimeError(f"Failed to render page {page_number}")

            image = images[0]
            image.save(image_directory / f"page_{page_number}.jpg", "JPEG")
            content = call_vision_model(client, encode_image_to_base64(image), model_name)
            with markdown_path.open("a", encoding="utf-8") as output:
                output.write(f"--- Page {page_number} ---\n{content.strip()}\n\n")
            progress.update(1)

    logger.info("Markdown written to %s", markdown_path)
    return markdown_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to Markdown with an OpenAI-compatible vision model."
    )
    parser.add_argument("pdf_path", help="Input PDF path")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    parser.add_argument("--dpi", type=int, default=300, help="Rendered page DPI")
    parser.add_argument("--poppler-path", help="Optional Poppler bin directory")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL"))
    parser.add_argument("--model", default=os.getenv("OPENAI_VISION_MODEL"))
    parser.add_argument(
        "--auth-mode",
        choices=("bearer", "none"),
        default=os.getenv("OPENAI_AUTH_MODE", "bearer"),
    )
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or OPENAI_BASE_URL is required")
    if not args.model:
        parser.error("--model or OPENAI_VISION_MODEL is required")
    if args.auth_mode == "bearer" and not args.api_key:
        parser.error("--api-key or OPENAI_API_KEY is required for bearer auth")
    if not 72 <= args.dpi <= 1200:
        parser.error("--dpi must be between 72 and 1200")
    return args


def main() -> int:
    args = parse_args()
    try:
        pdf_to_markdown(
            args.pdf_path,
            args.output,
            dpi=args.dpi,
            poppler_path=args.poppler_path,
            api_key=args.api_key,
            base_url=args.base_url,
            model_name=args.model,
            auth_mode=args.auth_mode,
        )
    except Exception as exc:
        logger.error("PDF conversion failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
