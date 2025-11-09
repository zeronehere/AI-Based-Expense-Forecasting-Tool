# backend/categorizer.py
"""
ENHANCED NLTK-BASED HYBRID CATEGORIZER
- Improved fN matching with better context understanding
- Enhanced fuzzy matching for typos and variations
- Better brand and subscription handling
- Comprehensive financial vocabulary
"""

import re
import numpy as np
from difflib import SequenceMatcher, get_close_matches
from collections import defaultdict
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from nltk import pos_tag
    
    # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
    
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        nltk.download('wordnet', quiet=True)
    
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        nltk.download('averaged_perceptron_tagger', quiet=True)
        
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

class AdvancedNLTCategorizer:
    def __init__(self):
        self.category_priority = {
            "Salary": 100, "Rent": 95, "Loan_Repayment": 90, "Insurance": 85,
            "Utilities": 80, "Healthcare": 75, "Education": 70, "Dining": 40,
            "Groceries": 35, "Entertainment": 30, "Transport": 25, 
            "Shopping": 20, "Travel": 15, "Miscellaneous": 50  # Increased priority for donations
        }
        
        # Initialize NLTK components
        if NLTK_AVAILABLE:
            self.stop_words = set(stopwords.words('english'))
            self.lemmatizer = WordNetLemmatizer()
            self.financial_stop_words = self._build_financial_stopwords()
        else:
            self.stop_words = set()
            self.lemmatizer = None
            self.financial_stop_words = set()
        
        self.category_patterns = self._build_enhanced_patterns()
        self.brand_context_rules = self._build_brand_context_rules()
        self.ml_model_ready = False
        self.setup_ml_model()
    
    def _build_financial_stopwords(self):
        """Extended financial stop words for better filtering"""
        financial_words = {
            'payment', 'bill', 'invoice', 'receipt', 'transaction', 'purchase',
            'order', 'subscription', 'monthly', 'annual', 'yearly', 'weekly',
            'daily', 'online', 'offline', 'digital', 'physical', 'store',
            'shop', 'buy', 'sell', 'spent', 'expense', 'income', 'money',
            'cash', 'card', 'debit', 'credit', 'bank', 'account', 'transfer',
            'amount', 'price', 'cost', 'fee', 'charge', 'paid', 'payment',
            'total', 'balance', 'refund', 'discount', 'tax', 'tip', 'due',
            'outstanding', 'cleared', 'pending', 'processed', 'completed'
        }
        return financial_words
    
    def _build_brand_context_rules(self):
        """Rules for brand-specific context categorization"""
        return {
            "amazon": {
                "primary_category": "Shopping",
                "context_keywords": {"prime", "subscription", "shopping", "order", "delivery"},
                "overrides": {
                    "prime video": "Entertainment",
                    "amazon music": "Entertainment", 
                    "kindle": "Shopping"
                }
            },
            "netflix": {
                "primary_category": "Entertainment",
                "context_keywords": {"subscription", "premium", "streaming"}
            },
            "spotify": {
                "primary_category": "Entertainment", 
                "context_keywords": {"premium", "subscription", "music"}
            },
            "zomato": {
                "primary_category": "Dining",
                "context_keywords": {"food", "order", "delivery", "restaurant"}
            },
            "swiggy": {
                "primary_category": "Dining",
                "context_keywords": {"food", "order", "delivery", "restaurant"}
            },
            "uber": {
                "primary_category": "Transport",
                "context_keywords": {"ride", "trip", "commute", "pool"},
                "overrides": {
                    "uber eats": "Dining"
                }
            }
        }
    
    def _build_enhanced_patterns(self):
        """Build comprehensive patterns with improved context understanding"""
        return {
            "Healthcare": {
                "exact_matches": {
                    "hospital", "doctor", "pharmacy", "medicine", "medical", "clinic",
                    "dental", "dentist", "optician", "glasses", "contacts", "lenses",
                    "physiotherapy", "therapy", "counseling", "psychologist", "psychiatrist",
                    "gym", "fitness", "yoga", "pilates", "workout", "exercise", "wellness",
                    "apollo", "max", "fortis", "manipal", "cult.fit"
                },
                "partial_matches": {
                    "health", "fitness", "wellness", "nutrition", "diet", "supplements",
                    "vitamins", "checkup", "appointment", "consultation", "treatment",
                    "recovery", "medical", "clinic", "healthcare", "dental", "optical",
                    "therapy", "counsel", "mental", "physical"
                },
                "context_words": {
                    "membership", "center", "club", "class", "session", "training",
                    "checkup", "scan", "test", "prescription", "medication"
                },
                "brands": {"apollo", "max healthcare", "fortis", "manipal", "cult.fit"}
            },
            
            "Entertainment": {
                "exact_matches": {
                    "netflix", "spotify", "youtube", "prime video", "hotstar",
                    "disney", "hulu", "apple tv", "zee5", "sonyliv", "altbalaji",
                    "mx player", "bookmyshow", "pvrcinemas", "inox", "cinema", "theater",
                    "concert", "show", "event", "game", "gaming", "playstation", "xbox",
                    "nintendo", "steam", "epic games", "movie", "music"
                },
                "partial_matches": {
                    "movie", "cinema", "theater", "concert", "show", "event",
                    "game", "gaming", "streaming", "music", "audio", "video",
                    "entertainment", "fun", "leisure", "recreation", "hobby"
                },
                "context_words": {
                    "subscription", "ticket", "booking", "premium", "membership",
                    "pass", "admission", "entry", "season", "episode", "stream"
                },
                "brands": {"netflix", "spotify", "hotstar", "bookmyshow", "sonyliv", "youtube"}
            },
            
            "Dining": {
                "exact_matches": {
                    "zomato", "swiggy", "ubereats", "foodpanda", "dominos", "pizza hut",
                    "mcdonald", "kfc", "burger king", "starbucks", "cafe coffee day",
                    "barista", "chaayos", "chai point", "third wave", "blue tokai",
                    "restaurant", "cafe", "diner", "pub", "bar", "food court"
                },
                "partial_matches": {
                    "restaurant", "cafe", "diner", "food", "meal", "lunch", "dinner",
                    "breakfast", "brunch", "buffet", "takeaway", "delivery", "eating",
                    "dining", "cuisine", "fast food", "fine dining", "casual dining"
                },
                "context_words": {
                    "order", "food court", "fast food", "fine dining", "casual dining",
                    "delivery", "takeout", "reservation", "table", "menu"
                },
                "brands": {"zomato", "swiggy", "dominos", "pizza hut", "mcdonald", "kfc", "starbucks"}
            },
            
            "Groceries": {
                "exact_matches": {
                    "bigbasket", "grocery", "supermarket", "dmart", "reliance fresh",
                    "more supermarket", "spar", "nature's basket", "food bazaar",
                    "vegetables", "fruits", "milk", "bread", "eggs", "rice", "wheat"
                },
                "partial_matches": {
                    "vegetables", "fruits", "milk", "bread", "eggs", "rice", "wheat",
                    "pulses", "spices", "oil", "ghee", "snacks", "beverages", "juice",
                    "water", "tea", "coffee", "sugar", "salt", "flour", "cereals",
                    "groceries", "provisions", "kitchen", "household", "daily needs"
                },
                "context_words": {
                    "shopping", "provisions", "kitchen", "daily needs", "household",
                    "supplies", "essentials", "monthly", "weekly", "stock"
                },
                "brands": {"bigbasket", "dmart", "reliance fresh", "more", "spar"}
            },
            
            "Transport": {
                "exact_matches": {
                    "uber", "ola", "rapido", "meru", "taxi", "bus", "metro", "train",
                    "flight", "indigo", "air india", "spicejet", "irctc", "fastag",
                    "petrol", "diesel", "cng", "fuel", "parking", "toll"
                },
                "partial_matches": {
                    "ride", "travel", "commute", "fuel", "petrol", "diesel", "cng",
                    "parking", "toll", "transport", "auto", "rickshaw", "cab",
                    "flight", "train", "bus", "metro", "travel", "journey"
                },
                "context_words": {
                    "booking", "ticket", "journey", "commuting", "traveling",
                    "fare", "fuel", "maintenance", "service", "repair"
                },
                "brands": {"uber", "ola", "rapido", "indigo", "air india", "irctc"}
            },
            
            "Shopping": {
                "exact_matches": {
                    "amazon", "flipkart", "myntra", "nykaa", "ajio", "meesho",
                    "snapdeal", "shopclues", "shopping", "mall", "outlet", "store",
                    "prime"  # Added prime for Amazon context
                },
                "partial_matches": {
                    "shopping", "purchase", "buy", "order", "clothes", "electronics",
                    "mobile", "laptop", "furniture", "home decor", "fashion", "beauty",
                    "apparel", "gadgets", "devices", "accessories", "cosmetics",
                    "subscription"  # Added subscription for shopping context
                },
                "context_words": {
                    "online", "offline", "retail", "store", "mall", "outlet",
                    "sale", "discount", "offer", "deal", "purchase", "buy",
                    "delivery", "shipping"  # Added delivery context
                },
                "brands": {"amazon", "flipkart", "myntra", "nykaa", "ajio"}
            },
            
            "Utilities": {
                "exact_matches": {
                    "electricity", "water bill", "gas bill", "internet", "broadband",
                    "wifi", "mobile", "phone", "recharge", "data pack", "jio", "airtel",
                    "vi", "bsnl", "act", "spectra", "tatasky", "airtel dth"
                },
                "partial_matches": {
                    "electric", "water", "gas", "internet", "mobile", "phone", "sim",
                    "broadband", "wifi", "cable", "dth", "utility", "bill", "recharge"
                },
                "context_words": {
                    "bill", "payment", "monthly", "plan", "subscription", "renewal",
                    "connection", "service", "provider", "recharge", "topup"
                },
                "brands": {"jio", "airtel", "vi", "bsnl", "tatasky", "act"}
            },
            
            "Rent": {
                "exact_matches": {
                    "rent", "lease", "apartment", "house rent", "flat rent", "room rent",
                    "pg", "hostel", "accommodation"
                },
                "partial_matches": {
                    "rent", "lease", "housing", "accommodation", "pg", "hostel",
                    "property", "real estate", "tenant", "landlord"
                },
                "context_words": {
                    "monthly", "advance", "security", "deposit", "maintenance",
                    "agreement", "contract", "tenancy"
                },
                "brands": set()
            },
            
            "Salary": {
                "exact_matches": {
                    "salary", "payroll", "paycheck", "stipend", "bonus", "incentive", 
                    "commission", "wages", "pay", "earnings"
                },
                "partial_matches": {
                    "salary", "income", "pay", "wages", "bonus", "incentive",
                    "earnings", "revenue", "compensation", "remuneration", "stipend"
                },
                "context_words": {
                    "credit", "deposit", "monthly", "company", "employer", "payroll",
                    "direct deposit", "bank transfer", "job", "work", "employment"
                },
                "brands": set()
            },
            
            "Loan_Repayment": {
                "exact_matches": {
                    "emi", "loan", "repayment", "credit card", "installment",
                    "mortgage", "home loan", "car loan", "personal loan"
                },
                "partial_matches": {
                    "loan", "emi", "repayment", "credit", "card payment", "dues",
                    "mortgage", "installment", "financing", "borrowing"
                },
                "context_words": {
                    "bank", "finance", "debt", "borrow", "outstanding", "due",
                    "payment", "settlement", "clearance"
                },
                "brands": {"hdfc", "icici", "sbi", "axis", "kotak"}
            },
            
            "Insurance": {
                "exact_matches": {
                    "insurance", "premium", "policy", "lic", "health insurance",
                    "life insurance", "car insurance", "home insurance"
                },
                "partial_matches": {
                    "insurance", "premium", "policy", "coverage", "protection",
                    "assurance", "indemnity", "underwriting"
                },
                "context_words": {
                    "life", "health", "car", "home", "term", "renewal",
                    "premium", "coverage", "claim", "benefit"
                },
                "brands": {"lic", "hdfc ergo", "icici lombard", "bajaj allianz"}
            },
            
            "Education": {
                "exact_matches": {
                    "school", "college", "tuition", "course", "books", "training",
                    "coaching", "university", "institute", "education"
                },
                "partial_matches": {
                    "education", "study", "learn", "course", "training", "coaching",
                    "tuition", "school", "college", "university", "learning"
                },
                "context_words": {
                    "fees", "student", "learning", "knowledge", "skills",
                    "certification", "degree", "diploma", "semester"
                },
                "brands": {"byju", "unacademy", "vedantu", "whitehat jr"}
            },
            
            "Travel": {
                "exact_matches": {
                    "flight", "hotel", "vacation", "holiday", "tour", "travel",
                    "trip", "booking", "makemytrip", "goibibo", "yatra"
                },
                "partial_matches": {
                    "travel", "trip", "journey", "vacation", "holiday", "tourism",
                    "flight", "hotel", "resort", "accommodation", "sightseeing"
                },
                "context_words": {
                    "booking", "sightseeing", "explore", "adventure", "resort",
                    "package", "itinerary", "destination", "tourist"
                },
                "brands": {"makemytrip", "goibibo", "yatra", "booking.com"}
            },
            
            "Miscellaneous": {
                "exact_matches": {
                    "donation", "charity", "gift", "tip", "cash", "transfer",
                    "personal", "general", "misc", "other", "various", "sundry",
                    "contribution", "fund", "ngo", "nonprofit", "non-profit", "cause",
                    "support", "help", "relief", "aid", "philanthropy", "giving"
                },
                "partial_matches": {
                    "donation", "charity", "gift", "tip", "cash", "transfer",
                    "personal", "general", "miscellaneous", "other", "various",
                    "contribution", "fund", "ngo", "nonprofit", "cause", "support",
                    "help", "relief", "aid", "philanthropy", "giving"
                },
                "context_words": {
                    "help", "support", "contribution", "fund", "cause", "organization",
                    "ngo", "nonprofit", "voluntary", "giving", "philanthropy",
                    "charitable", "donate", "sponsor", "beneficiary"
                },
                "brands": set()
            }
        }
    
    def advanced_text_processing(self, text):
        """Advanced NLP text processing using NLTK"""
        if not NLTK_AVAILABLE or not text:
            return set(), ""
        
        try:
            # Convert to lowercase
            text = text.lower()
            
            # Remove special characters but keep important ones
            text = re.sub(r'[^\w\s@.-]', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Tokenize
            tokens = word_tokenize(text)
            
            # Remove stop words (both general and financial)
            filtered_tokens = [
                token for token in tokens 
                if token not in self.stop_words and token not in self.financial_stop_words
            ]
            
            # Lemmatization (convert to base form)
            lemmatized_tokens = [
                self.lemmatizer.lemmatize(token) for token in filtered_tokens
            ]
            
            # Part-of-speech tagging to identify nouns and verbs
            pos_tags = pos_tag(lemmatized_tokens)
            
            # Focus on nouns and verbs (most meaningful for categorization)
            meaningful_tokens = [
                token for token, pos in pos_tags 
                if pos.startswith('N') or pos.startswith('V')  # Nouns or Verbs
            ]
            
            # Also include brand names and specific terms
            brand_tokens = [token for token in lemmatized_tokens if len(token) > 2]
            
            # Combine meaningful tokens with brand tokens
            all_tokens = set(meaningful_tokens + brand_tokens)
            
            # Create processed text for ML
            processed_text = ' '.join(all_tokens)
            
            return all_tokens, processed_text
            
        except Exception as e:
            # Fallback to basic processing
            print(f"NLTK processing failed: {e}")
            basic_tokens = set(re.findall(r'\b\w+\b', text.lower()))
            basic_tokens = basic_tokens - self.financial_stop_words
            return basic_tokens, ' '.join(basic_tokens)
    
    def calculate_semantic_similarity(self, text1, text2):
        """Calculate semantic similarity between two texts"""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def apply_brand_context_rules(self, description, tokens):
        """Apply brand-specific context rules for better categorization"""
        desc_lower = description.lower()
        
        for brand, rules in self.brand_context_rules.items():
            if brand in desc_lower:
                # Check for brand-specific overrides first
                if "overrides" in rules:
                    for override_pattern, override_category in rules["overrides"].items():
                        if override_pattern in desc_lower:
                            return override_category, "very-high"
                
                # Check if context keywords match
                context_matches = any(keyword in desc_lower for keyword in rules["context_keywords"])
                if context_matches:
                    return rules["primary_category"], "high"
                else:
                    return rules["primary_category"], "medium"
        
        return None, None
    
    def enhanced_fuzzy_match(self, token, pattern_list, threshold=0.7):
        """Enhanced fuzzy matching with better threshold handling"""
        if not token or not pattern_list:
            return None, 0.0
        
        # First try exact match
        if token in pattern_list:
            return token, 1.0
        
        # Then try contains match
        for pattern in pattern_list:
            if token in pattern or pattern in token:
                return pattern, 0.9
        
        # Finally try fuzzy matching
        matches = get_close_matches(token, pattern_list, n=1, cutoff=threshold)
        if matches:
            similarity = SequenceMatcher(None, token, matches[0]).ratio()
            return matches[0], similarity
        
        return None, 0.0
    
    def rule_based_categorize(self, description):
        """Enhanced rule-based categorization with brand context and fuzzy matching"""
        if not description:
            return "Uncategorized", "low"
        
        description_lower = description.lower()
        
        # FIX: Special handling for donation and charity - HIGHEST PRIORITY
        donation_keywords = [
            "donation", "charity", "donate", "contribution", "fund", 
            "ngo", "nonprofit", "non-profit", "cause", "support",
            "help", "relief", "aid", "philanthropy", "giving"
        ]
        
        # Check if any donation keyword exists in description
        for keyword in donation_keywords:
            if keyword in description_lower:
                return "Miscellaneous", "very-high"
        
        # Apply brand context rules first (highest priority)
        brand_category, brand_confidence = self.apply_brand_context_rules(description, set())
        if brand_category and brand_confidence in ["very-high", "high"]:
            return brand_category, brand_confidence
        
        # Advanced text processing
        tokens, processed_text = self.advanced_text_processing(description)
        
        if not tokens:
            return "Uncategorized", "low"
        
        category_scores = defaultdict(float)
        
        for category, patterns in self.category_patterns.items():
            score = 0.0
            
            # Strategy 1: Exact matches (highest weight)
            exact_matches = tokens.intersection(patterns["exact_matches"])
            score += len(exact_matches) * 4.0
            
            # Strategy 2: Brand matches (high weight)
            brand_matches = tokens.intersection(patterns["brands"])
            score += len(brand_matches) * 3.5
            
            # Strategy 3: Enhanced fuzzy partial matches
            for token in tokens:
                for pattern in patterns["partial_matches"]:
                    similarity = self.calculate_semantic_similarity(token, pattern)
                    if similarity > 0.85:  # Very similar
                        score += 3.0
                    elif similarity > 0.75:  # Similar
                        score += 2.0
                    elif similarity > 0.65:  # Somewhat similar
                        score += 1.0
                    elif token in pattern or pattern in token:  # Contains
                        score += 1.5
            
            # Strategy 4: Context words
            context_matches = tokens.intersection(patterns["context_words"])
            score += len(context_matches) * 1.5
            
            # Strategy 5: Check if description contains key phrases
            for exact in patterns["exact_matches"]:
                if exact in description_lower:
                    score += 2.0
            for brand in patterns["brands"]:
                if brand in description_lower:
                    score += 2.5
            
            if score > 0:
                # Apply category priority boost
                priority_boost = self.category_priority.get(category, 1) / 100
                final_score = score * (1 + priority_boost)
                category_scores[category] = final_score
        
        # Apply brand context as tie-breaker if we have medium confidence
        if brand_category and brand_confidence == "medium" and category_scores:
            category_scores[brand_category] += 2.0
        
        if category_scores:
            # Get best category
            best_category, best_score = max(category_scores.items(), key=lambda x: x[1])
            
            # Determine confidence based on score
            if best_score >= 8.0:
                confidence = "very-high"
            elif best_score >= 5.0:
                confidence = "high"
            elif best_score >= 3.0:
                confidence = "medium"
            elif best_score >= 1.5:
                confidence = "low"
            else:
                confidence = "very-low"
            
            return best_category, confidence
        
        return "Uncategorized", "low"
    
    def setup_ml_model(self):
        """Initialize ML model with comprehensive training data"""
        try:
            self.training_data = self._create_training_data()
            self.ml_model_ready = True
        except Exception as e:
            print(f"ML model setup failed: {e}")
            self.ml_model_ready = False
    
    def _create_training_data(self):
        """Create extensive training data for ML fallback"""
        training_examples = {}
        
        for category, patterns in self.category_patterns.items():
            examples = set()
            
            # Add all patterns
            examples.update(patterns["exact_matches"])
            examples.update(patterns["partial_matches"])
            examples.update(patterns["brands"])
            
            # Create realistic combinations
            for exact in list(patterns["exact_matches"])[:15]:
                for partial in list(patterns["partial_matches"])[:10]:
                    examples.add(f"{exact} {partial}")
                for context in list(patterns["context_words"])[:5]:
                    examples.add(f"{exact} {context}")
                for brand in list(patterns["brands"])[:3]:
                    examples.add(f"{exact} {brand}")
            
            # Add comprehensive real-world examples
            examples.update(self._get_comprehensive_examples(category))
            
            training_examples[category] = list(examples)[:100]
        
        return training_examples
    
    def _get_comprehensive_examples(self, category):
        """Get comprehensive real-world transaction examples"""
        real_examples = {
            "Healthcare": {
                "gym membership monthly fee", "yoga class session payment", "doctor appointment consultation",
                "medicine purchase pharmacy", "fitness center membership", "health checkup diagnostic",
                "medical consultation specialist", "pharmacy bill medicines", "dental checkup cleaning",
                "optical glasses prescription", "physiotherapy session treatment", "mental health counseling"
            },
            "Entertainment": {
                "netflix monthly subscription", "movie tickets cinema hall", "concert booking live show",
                "spotify premium music streaming", "gaming subscription steam", "cinema show movie night",
                "streaming service entertainment", "music subscription audio", "video game purchase digital",
                "theater play performance tickets", "youtube premium subscription"
            },
            "Shopping": {
                "amazon prime subscription", "amazon shopping order", "flipkart electronics purchase",
                "myntra fashion shopping", "nykaa beauty products", "ajio clothes order",
                "online shopping delivery", "amazon subscription renewal", "shopping mall purchase"
            },
            "Dining": {
                "zomato food delivery", "swiggy lunch order", "restaurant dinner with friends",
                "starbucks coffee break", "mcdonald burger meal", "pizza hut delivery",
                "cafe coffee meeting", "food court lunch", "ubereats dinner order"
            },
            "Transport": {
                "uber ride to office", "ola auto commute", "rapido bike ride",
                "petrol fill station", "bus ticket daily", "metro card recharge",
                "flight booking delhi", "train ticket irctc", "taxi fare payment"
            },
            "Utilities": {
                "electricity bill payment", "water bill monthly", "gas bill quarter",
                "jio mobile recharge", "airtel broadband bill", "wifi internet payment",
                "mobile phone bill", "tatasky dth recharge", "internet service provider"
            },
            "Miscellaneous": {
                "charity donation to red cross", "donation for cancer research", "ngo contribution",
                "cash gift for birthday", "personal transfer to friend", "tip for delivery",
                "philanthropy donation", "relief fund contribution", "nonprofit support",
                "cash donation", "online charity contribution", "fundraiser donation"
            }
        }
        return real_examples.get(category, set())
    
    def ml_similarity_categorize(self, description):
        """Machine learning fallback using advanced text processing"""
        if not self.ml_model_ready:
            return "Uncategorized", "low"
        
        try:
            # Process the input description
            _, processed_desc = self.advanced_text_processing(description)
            
            if not processed_desc:
                return "Uncategorized", "low"
            
            # Prepare all training texts
            all_texts = []
            category_labels = []
            
            for category, examples in self.training_data.items():
                for example in examples:
                    _, processed_example = self.advanced_text_processing(example)
                    if processed_example:
                        all_texts.append(processed_example)
                        category_labels.append(category)
            
            if not all_texts:
                return "Uncategorized", "low"
            
            # Add the query description
            all_texts.append(processed_desc)
            
            # Vectorize using TF-IDF
            tfidf = TfidfVectorizer(
                max_features=2000, 
                stop_words='english', 
                min_df=1,
                ngram_range=(1, 2)
            )
            tfidf_matrix = tfidf.fit_transform(all_texts)
            
            # Calculate similarities
            query_vector = tfidf_matrix[-1]
            training_vectors = tfidf_matrix[:-1]
            
            similarities = cosine_similarity(query_vector, training_vectors)[0]
            
            # Find best matches (top 3)
            top_indices = np.argsort(similarities)[-3:][::-1]
            top_similarities = similarities[top_indices]
            top_categories = [category_labels[i] for i in top_indices]
            
            # Weighted voting based on similarity scores
            category_votes = defaultdict(float)
            for cat, sim in zip(top_categories, top_similarities):
                category_votes[cat] += sim
            
            # Get best category
            if category_votes:
                best_category = max(category_votes.items(), key=lambda x: x[1])[0]
                best_similarity = category_votes[best_category] / len(top_indices)
                
                # Determine confidence
                if best_similarity > 0.6:
                    confidence = "high"
                elif best_similarity > 0.4:
                    confidence = "medium"
                elif best_similarity > 0.2:
                    confidence = "low"
                else:
                    return "Uncategorized", "low"
                    
                return best_category, confidence
                
        except Exception as e:
            print(f"ML categorization failed: {e}")
        
        return "Uncategorized", "low"
    
    def generate_intelligent_suggestions(self, description, primary_category):
        """Generate intelligent alternative category suggestions"""
        if primary_category == "Uncategorized":
            return ["Shopping", "Miscellaneous", "Entertainment"]
        
        tokens, _ = self.advanced_text_processing(description)
        
        suggestions = []
        scores = {}
        
        for category, patterns in self.category_patterns.items():
            if category == primary_category:
                continue
            
            score = 0
            
            # Check for connections to this category
            if tokens.intersection(patterns["exact_matches"]):
                score += 3
            if tokens.intersection(patterns["brands"]):
                score += 2.5
            if tokens.intersection(patterns["partial_matches"]):
                score += 2
            if tokens.intersection(patterns["context_words"]):
                score += 1
            
            if score > 0:
                scores[category] = score
        
        # Return top 3 suggestions by score
        sorted_suggestions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [cat for cat, score in sorted_suggestions[:3]]
    
    def categorize(self, description):
        """
        Main categorization function - Enhanced Hybrid approach
        Returns: (category, confidence, suggestions)
        """
        if not description or len(description.strip()) < 2:
            return "Uncategorized", "low", ["Shopping", "Miscellaneous"]
        
        # Step 1: Enhanced NLTK-powered rule-based categorization
        category, confidence = self.rule_based_categorize(description)
        
        # Step 2: If rule-based has low confidence, try ML
        if category == "Uncategorized" or confidence in ["low", "very-low"]:
            ml_category, ml_confidence = self.ml_similarity_categorize(description)
            if ml_category != "Uncategorized" and ml_confidence in ["high", "medium"]:
                category, confidence = ml_category, ml_confidence
        
        # Step 3: Generate intelligent suggestions
        suggestions = self.generate_intelligent_suggestions(description, category)
        
        return category, confidence, suggestions

# Global instance for easy import
advanced_categorizer = AdvancedNLTCategorizer()

def categorize(description: str):
    """
    Main categorization function for external use
    Returns: (category, confidence, suggestions)
    """
    return advanced_categorizer.categorize(description)

# Enhanced test function
def test_enhanced_categorization():
    """Test the enhanced NLTK categorizer with various inputs"""
    test_cases = [
        "donation",  # Should be Miscellaneous
        "charity contribution",  # Should be Miscellaneous
        "ngo donation",  # Should be Miscellaneous
        "amazon subscription",
        "amazon prime subscription", 
        "netflix subscription",
        "spotify premium",
        "zomato food order",
        "uber ride to office",
        "bigbasket grocery delivery",
        "electricity bill payment",
        "gym membership fee",
        "movie tickets booking",
        "starbucks coffee",
        "mobile recharge jio",
        "rent payment",
        "school fees",
        "doctor appointment",
        "salary deposit",  # Should be Salary
        "bonus payment"  # Should be Salary
    ]
    
    print("🧪 Testing Enhanced NLTK Categorizer:")
    print("=" * 70)
    print(f"🤖 NLTK Available: {NLTK_AVAILABLE}")
    print("=" * 70)
    
    for test in test_cases:
        category, confidence, suggestions = categorize(test)
        print(f"📝 '{test}'")
        print(f"   🎯 {category} ({confidence})")
        if suggestions:
            print(f"   💡 Suggestions: {suggestions}")
        print()

if __name__ == "__main__":
    test_enhanced_categorization()