import base64
import logging
import os
from io import BytesIO

from openai import OpenAI
from pdf2image import convert_from_path
from tqdm import tqdm


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def encode_image(image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def process_pdf(
    pdf_path: str,
    api_key: str,
    base_url: str,
    model: str = "qwen-vl-max",
) -> None:
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    image_directory = os.path.join("static", "pages")
    os.makedirs(image_directory, exist_ok=True)
    output_path = f"{base_name}.txt"

    client = OpenAI(api_key=api_key, base_url=base_url)
    with open(output_path, "w", encoding="utf-8") as output:
        output.write(f"# Source: {base_name}\n\n")

    page_number = 1
    progress = tqdm(desc="PDF vision parsing")
    while True:
        try:
            images = convert_from_path(
                pdf_path,
                first_page=page_number,
                last_page=page_number,
                dpi=200,
            )
            if not images:
                break

            image = images[0]
            image.save(os.path.join(image_directory, f"page_{page_number}.jpg"), "JPEG")
            encoded_image = encode_image(image)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Convert this textbook page to Markdown. Preserve the original "
                                    "text and structure, use LaTeX for formulas, and describe diagrams "
                                    "or charts precisely."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                },
                            },
                        ],
                    }
                ],
            )

            content = response.choices[0].message.content or ""
            with open(output_path, "a", encoding="utf-8") as output:
                output.write(f"\n\n--- Page {page_number} ---\n\n{content}\n")

            page_number += 1
            progress.update(1)
        except Exception as exc:
            logger.error("Failed to parse page %s: %s", page_number, exc)
            break

    progress.close()
    logger.info("PDF conversion completed: %s", output_path)


if __name__ == "__main__":
    configured_api_key = os.getenv("OPENAI_API_KEY")
    if not configured_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    process_pdf(
        pdf_path=os.getenv("PDF_PATH", "book1.pdf"),
        api_key=configured_api_key,
        base_url=os.getenv(
            "OPENAI_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("OPENAI_VISION_MODEL", "qwen-vl-max"),
    )
