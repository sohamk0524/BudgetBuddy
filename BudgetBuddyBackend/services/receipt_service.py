"""
Receipt scanning service — uses Claude Vision to analyze receipt images.
"""

import anthropic
import base64
import json


def analyze_receipt(image_data: bytes, media_type: str) -> dict:
    """
    Analyze a receipt image using Claude Vision.

    Args:
        image_data: Raw image bytes (JPEG, PNG, or HEIC)
        media_type: MIME type string, e.g. "image/jpeg"

    Returns:
        Dict with keys: merchant, date, total, items (each with classification)
    """
    client = anthropic.Anthropic()
    prompt = """Analyze this receipt image. Extract:
1. Merchant name and total amount
2. The date of the transaction (from the receipt header/footer) in YYYY-MM-DD format. If no date is visible, use null.
3. Every line item with its price
4. Classify each item into exactly one of: "food" (prepared meals, restaurant food), "drink" (coffee, alcohol, beverages), "groceries" (raw ingredients, produce, packaged goods at a grocery/supermarket), "transportation", "entertainment", or "other"

Respond ONLY with valid JSON in exactly this format:
{
  "merchant": "string",
  "date": "YYYY-MM-DD" or null,
  "total": <float>,
  "items": [{"name": "string", "price": <float>, "classification": "food" or "drink" or "groceries" or "transportation" or "entertainment" or "other"}]
}"""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.standard_b64encode(image_data).decode(),
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )

    response_text = msg.content[0].text
    # Strip markdown code fences if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    result = json.loads(response_text.strip())

    # Normalise any unrecognised item classifications (e.g. legacy "essential"/"discretionary")
    valid = {'food', 'drink', 'groceries', 'transportation', 'entertainment', 'other'}
    for item in result.get('items', []):
        cls = (item.get('classification') or '').lower()
        if cls not in valid:
            item['classification'] = _fallback_classification(cls)

    return result


def _fallback_classification(cls: str) -> str:
    """Map legacy or unrecognised classification strings to a valid category."""
    if cls == 'essential':
        return 'groceries'
    if cls == 'discretionary':
        return 'food'
    return 'other'
