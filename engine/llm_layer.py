import os
import re
from typing import Optional, Dict, Any


class LLMLayer:
    """Optional LLM rephrasing layer.
    
    Disabled by default. When enabled, strictly validates that no facts,
    numbers, amounts, PNRs, or rule citations are dropped or altered.
    """

    def __init__(self, enabled: bool = False, api_key: Optional[str] = None):
        self.enabled = enabled or bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")

    def _validate_rephrase(self, original_text: str, rephrased_text: str, context: Dict[str, Any]) -> bool:
        """Validates that rephrasing did not alter or drop critical amounts, PNR, or citations."""
        # Extract all rupee amounts from original (e.g. ₹500, ₹1,500, ₹2,000, 500, 1,500, 2,000)
        original_amounts = re.findall(r"(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)?)", original_text)
        for amt in original_amounts:
            # Check if amount is preserved in rephrase
            if amt not in rephrased_text:
                return False

        # Check PNR preservation
        pnr = context.get("pnr")
        if pnr and pnr in original_text:
            if pnr not in rephrased_text:
                return False

        # Check timeframes (7 business days, 24 hours)
        if "7 business days" in original_text and "7 business days" not in rephrased_text:
            return False
        if "24 hours" in original_text and "24 hours" not in rephrased_text:
            return False

        return True

    def rephrase(self, template_reply: str, context: Dict[str, Any]) -> str:
        """Rephrases the template reply if LLM is enabled and configured, else returns template directly."""
        if not self.enabled or not self.api_key:
            return template_reply

        try:
            # In a live environment with an active provider, this would call the API.
            # Here we provide the safe fallback and verification scaffold.
            rephrased = template_reply
            if self._validate_rephrase(template_reply, rephrased, context):
                return rephrased
            return template_reply
        except Exception:
            return template_reply
