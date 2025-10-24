# backend/categorizer.py
import re
import difflib
from collections import Counter

# Basic category keywords (expandable)
CATEGORY_KEYWORDS = {
    "Groceries": ["grocery", "supermarket", "mart", "grocer", "vegetable", "bakery"],
    "Transport": ["petrol", "fuel", "gas station", "uber", "ola", "taxi", "bus", "metro", "train", "parking"],
    "Dining": ["restaurant", "dinner", "lunch", "breakfast", "cafe", "coffee", "bar", "food", "eat"],
    "Rent": ["rent", "apartment", "house rent", "lease"],
    "Utilities": ["electricity", "water bill", "internet", "gas bill", "utility", "utility bill"],
    "Entertainment": ["movie", "netflix", "spotify", "entertainment", "concert", "theatre"],
    "Healthcare": ["hospital", "doctor", "clinic", "medical", "pharmacy", "medicine"],
    "Education": ["tuition", "school", "college", "university", "course", "exam", "education"],
    "Insurance": ["insurance", "premium", "policy"],
    "Loan_Repayment": ["loan", "emi", "repayment", "mortgage"],
    "Salary": ["salary", "payroll", "credit", "credited", "salary deposit"],
    "Shopping": ["shopping", "mall", "amazon", "flipkart", "store", "purchase"],
    "Travel": ["flight", "hotel", "booking", "travel", "airbnb", "bus booking", "train booking"],
    "Miscellaneous": ["misc", "miscellaneous", "other", "fee", "charges"]
}

# Flatten keyword set for fuzzy matching
ALL_KEYWORDS = {kw: cat for cat, kws in CATEGORY_KEYWORDS.items() for kw in kws}
KEYWORDS_LIST = list(ALL_KEYWORDS.keys())

PUNCT_RE = re.compile(r"[^\w\s]")

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def keyword_score(tokens, category):
    """Count how many keywords for a category appear in tokens."""
    kws = CATEGORY_KEYWORDS.get(category, [])
    score = 0
    for kw in kws:
        # check token-level containment and phrase containment
        if kw in " ".join(tokens):
            score += 2  # phrase match weight
        else:
            for t in tokens:
                if kw == t:
                    score += 1
    return score

def fuzzy_token_match(token, cutoff=0.85):
    """Return a matching keyword (if any) using difflib."""
    matches = difflib.get_close_matches(token, KEYWORDS_LIST, n=1, cutoff=cutoff)
    return matches[0] if matches else None

def categorize(description: str):
    """
    Return a tuple (category, confidence_score, suggestions_list)
    - category: chosen category string (or 'Uncategorized')
    - confidence_score: 'high'|'medium'|'low'
    - suggestions_list: list of alternative categories (top 3)
    """
    text = normalize_text(description)
    tokens = text.split()
    if not tokens:
        return ("Uncategorized", "low", ["Uncategorized"])

    # Exact keyword/phrase search (highest priority)
    cat_scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat in CATEGORY_KEYWORDS:
        cat_scores[cat] = keyword_score(tokens, cat)

    # If we have direct hits, pick best
    best_cat, best_score = max(cat_scores.items(), key=lambda kv: kv[1])
    suggestions = []

    if best_score > 0:
        # build suggestions sorted by score
        sorted_cats = sorted(cat_scores.items(), key=lambda kv: kv[1], reverse=True)
        suggestions = [c for c, s in sorted_cats if s > 0][:5]
        # interpret confidence
        if best_score >= 3:
            confidence = "high"
        else:
            confidence = "medium"
        return (best_cat, confidence, suggestions)

    # No direct hits; try fuzzy token matching
    fuzzy_matches = []
    for t in tokens:
        fm = fuzzy_token_match(t, cutoff=0.8)
        if fm:
            fuzzy_matches.append(ALL_KEYWORDS.get(fm))

    # Count fuzzy occurrences
    if fuzzy_matches:
        counter = Counter(fuzzy_matches)
        best_cat, cnt = counter.most_common(1)[0]
        suggestions = [c for c, _ in counter.most_common(5)]
        confidence = "medium" if cnt >= 2 else "low"
        return (best_cat, confidence, suggestions)

    # Last resort: try to match any token to keywords with lower cutoff
    for t in tokens:
        fm = fuzzy_token_match(t, cutoff=0.6)
        if fm:
            return (ALL_KEYWORDS.get(fm), "low", [ALL_KEYWORDS.get(fm)])

    # Nothing found
    return ("Uncategorized", "low", ["Uncategorized"])
