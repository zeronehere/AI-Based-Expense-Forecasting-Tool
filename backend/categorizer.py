# backend/categorizer.py
# Simple keyword-based categorizer for transactions.
# This file must define a function named `categorize(description: str) -> str`.

CATEGORY_KEYWORDS = {
    "Groceries": ["grocery", "supermarket", "mart", "bigbasket", "grocer", "store"],
    "Transport": ["uber", "ola", "taxi", "bus", "metro", "fuel", "petrol", "ride"],
    "Rent": ["rent", "landlord"],
    "Utilities": ["electricity", "water", "internet", "wifi", "phone", "bill"],
    "Dining": ["restaurant", "cafe", "dinner", "lunch", "food", "pizza", "burger"],
    "Entertainment": ["netflix", "movie", "spotify", "concert", "play"],
    "Salary": ["salary", "payroll", "income", "pay"],
}

def categorize(description: str) -> str:
    """
    Return a category string based on matching keywords inside description.
    If no keyword matches, return "Other" or "Uncategorized" for empty descriptions.
    """
    if not description:
        return "Uncategorized"
    desc = str(description).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                return cat
    return "Other"
# backend/categorizer.py
# Improved categorizer: keyword matching + fuzzy token matching fallback

from difflib import get_close_matches
import re

CATEGORY_KEYWORDS = {
    "Groceries": ["grocery", "supermarket", "mart", "bigbasket", "grocer", "store"],
    "Transport": ["uber", "ola", "taxi", "bus", "metro", "fuel", "petrol", "ride"],
    "Rent": ["rent", "landlord"],
    "Utilities": ["electricity", "water", "internet", "wifi", "phone", "bill"],
    "Dining": ["restaurant", "cafe", "dinner", "lunch", "food", "pizza", "burger"],
    "Entertainment": ["netflix", "movie", "spotify", "concert", "play"],
    "Salary": ["salary", "payroll", "income", "pay"],
    "Health": ["hospital", "clinic", "doctor", "pharmacy", "medicine"],
    "Shopping": ["amazon", "flipkart", "purchase", "order", "shop"],
    "Travel": ["flight", "hotel", "booking", "airbnb", "train"],
}

# Flatten keywords for fuzzy matching
ALL_KEYWORDS = []
for cat, kws in CATEGORY_KEYWORDS.items():
    ALL_KEYWORDS.extend(kws)

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")

def _tokens(text):
    return TOKEN_RE.findall(str(text).lower())

def categorize(description: str) -> str:
    """
    Return category based on:
    1) direct keyword containment
    2) token-level fuzzy matching (difflib.get_close_matches)
    3) fallback to 'Other' or 'Uncategorized'
    """
    if not description or not str(description).strip():
        return "Uncategorized"
    desc = str(description).lower()

    # 1) direct containment by keywords for each category
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                return cat

    # 2) tokenize description and try fuzzy match against keywords
    tokens = _tokens(description)
    for t in tokens:
        # get_close_matches returns list of close keywords (max 1, cutoff 0.75)
        matches = get_close_matches(t, ALL_KEYWORDS, n=1, cutoff=0.78)
        if matches:
            match = matches[0]
            # find category for match
            for cat, kws in CATEGORY_KEYWORDS.items():
                if match in kws:
                    return cat

    # 3) fallback
    return "Other"
