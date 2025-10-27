# backend/categorizer.py
"""
Automated transaction categorization using:
1. Rule-based keyword matching
2. NLP similarity fallback (TF-IDF + cosine similarity)
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CATEGORY_EXAMPLES = {
    "Groceries": [
        # Supermarkets & Hypermarkets
        "walmart", "target", "kroger", "safeway", "aldi", "costco", "sam's club", "whole foods",
        "trader joe's", "publix", "stop & shop", "food lion", "wegmans", "heb", "giant eagle",
        "bigbasket", "dmart", "reliance fresh", "more supermarket", "spar", "nature's basket",
        "food bazaar", "easyday", "star bazaar", "vishal megamart", "apna bazaar", "safal",
        "hypercity", "spencer's", "foodworld", "freshpik", "smart bazaar",
        
        # Indian Kirana & Local Stores
        "kirana", "general store", "provision store", "local market", "mandi", "sabzi mandi",
        "vegetable market", "fruit vendor", "fish market", "meat shop", "chicken shop",
        "milk dairy", "bread shop", "bakery", "sweet shop", "pan shop", "tea stall",
        
        # Food Items & Categories
        "grocery", "supermarket", "vegetables", "fruits", "milk", "bread", "dairy", "eggs",
        "meat", "fish", "chicken", "poultry", "rice", "wheat", "atta", "flour", "pulse", "dal",
        "lentils", "spices", "masala", "oil", "ghee", "butter", "cheese", "yogurt", "curd",
        "snacks", "biscuits", "chips", "namkeen", "chocolate", "sweets", "beverages", "juice",
        "cold drink", "soda", "water bottle", "tea", "coffee", "sugar", "salt", "flour",
        "cereals", "breakfast", "pasta", "noodles", "sauce", "pickle", "jam", "honey"
    ],

    "Transport": [
        # Ride Sharing & Taxis
        "uber", "ola", "lyft", "rapido", "meru", "quick ride", "ola auto", "uber auto",
        "ola bike", "uber moto", "ola share", "uber pool", "ola outstation", "uber rent",
        "taxi", "cab", "radio taxi", "premium taxi", "luxury cab",
        
        # Public Transport
        "bus", "metro", "train", "local train", "subway", "monorail", "public transport",
        "bus pass", "metro card", "travel card", "commuter pass", "season ticket",
        "auto", "rickshaw", "tuk tuk", "cycle rickshaw", "tanga", "shared auto",
        
        # Fuel & Vehicle Maintenance
        "petrol", "diesel", "fuel", "gasoline", "cng", "lpg", "charging", "ev charging",
        "battery", "tyre", "tire", "car service", "bike service", "vehicle repair",
        "maintenance", "oil change", "car wash", "bike wash", "spare parts", "accessories",
        
        # Parking & Tolls
        "parking", "toll", "fastag", "expressway", "highway", "bridge toll", "parking fee",
        "valet parking", "multi-level parking",
        
        # Airlines & Railways
        "airport taxi", "railway taxi", "station auto", "bus stand", "depot"
    ],

    "Dining": [
        # Food Delivery Apps
        "zomato", "swiggy", "ubereats", "doordash", "grubhub", "foodpanda", "dominos",
        "pizza hut", "box8", "faasos", "behrouz", "ovenstory", "freshmenu",
        
        # Restaurant Chains
        "mcdonald", "kfc", "burger king", "subway", "domino's", "pizza hut", "starbucks",
        "cafe coffee day", "barista", "costa", "dunkin", "baskin robbins", "dunkin donuts",
        "bikanervala", "haldiram", "britannia", "chaayos", "chai point", "third wave",
        "blue tokai", "sattviko", "natural's", "freshpress", "eatfit",
        
        # Restaurant Types
        "restaurant", "cafe", "diner", "bistro", "food court", "takeaway", "delivery",
        "drive thru", "fast food", "quick service", "fine dining", "casual dining",
        "buffet", "brunch", "breakfast", "lunch", "dinner", "supper", "meal",
        
        # Cuisine Types
        "indian", "chinese", "italian", "mexican", "thai", "continental", "south indian",
        "north indian", "punjabi", "bengali", "gujarati", "maharashtrian", "andhra",
        "kerala", "tamil", "mughlai", "awadhi", "rajasthani", "street food",
        
        # Specific Foods
        "pizza", "burger", "sandwich", "pasta", "noodles", "biryani", "curry", "rice",
        "roti", "naan", "paratha", "dosa", "idli", "vada", "sambar", "chutney",
        "ice cream", "dessert", "sweets", "cake", "pastry", "bakery", "coffee", "tea",
        "shake", "smoothie", "juice", "mocktail", "cold coffee"
    ],

    "Rent": [
        "rent", "lease", "apartment rent", "house rent", "flat rent", "room rent",
        "office rent", "shop rent", "commercial rent", "residential rent",
        "tenant", "landlord", "security deposit", "maintenance charges",
        "society maintenance", "housing", "accommodation", "pg", "paying guest",
        "hostel", "lodging", "boarding", "monthly rent", "advance rent",
        "property", "real estate", "brokerage", "agent commission"
    ],

    "Utilities": [
        # Electricity & Water
        "electricity", "electric bill", "power bill", "water bill", "municipal water",
        "borewell", "sewage", "drainage", "property tax", "house tax",
        
        # Internet & Telecom
        "internet", "wifi", "broadband", "fiber", "airtel", "jio", "vodafone", "idea",
        "bsnl", "reliance jio", "mobile", "phone", "telephone", "postpaid", "prepaid",
        "recharge", "data pack", "calling card", "sim card",
        
        # Gas & Fuel
        "gas", "lpg", "cylinder", "indane", "bharat gas", "hp gas", "cooking gas",
        "piped gas", "cng", "pipeline",
        
        # TV & Subscriptions
        "cable", "dth", "tatasky", "airtel dth", "dish tv", "sun direct", "reliance digital",
        "netflix", "prime video", "hotstar", "sonyliv", "youtube premium", "spotify",
        "apple music", "gaana", "jiosaavn", "wynk", "amazon prime",
        
        # Other Utilities
        "newspaper", "magazine", "milk delivery", "newspaper delivery"
    ],

    "Entertainment": [
        # Streaming Services
        "netflix", "prime video", "hotstar", "sonyliv", "youtube premium", "disney",
        "hulu", "apple tv", "zee5", "voot", "altbalaji", "mx player",
        
        # Music & Audio
        "spotify", "apple music", "gaana", "jiosaavn", "wynk", "hungama", "saavn",
        "pandora", "soundcloud", "audio subscription",
        
        # Movies & Theaters
        "movie", "cinema", "pvr", "inox", "carnival", "imax", "film", "show", "ticket",
        "bookmyshow", "paytm movies", "movie booking", "theater", "multiplex",
        
        # Events & Shows
        "concert", "live show", "theatre", "play", "drama", "comedy show", "standup",
        "event", "exhibition", "fair", "festival", "cultural event",
        
        # Games & Hobbies
        "game", "gaming", "playstation", "xbox", "nintendo", "steam", "epic games",
        "mobile game", "online game", "arcade", "gaming zone", "virtual reality",
        
        # Sports & Recreation
        "sports", "cricket", "football", "badminton", "tennis", "swimming", "gym",
        "fitness", "yoga", "meditation", "adventure", "amusement park", "water park",
        "bowling", "pool", "snooker", "darts"
    ],

    "Healthcare": [
        # Hospitals & Clinics
        "hospital", "clinic", "medical center", "healthcare", "diagnostic center",
        "nursing home", "polyclinic", "multispecialty", "super specialty",
        "apollo", "max hospital", "fortis", "manipal", "artemis", "medanta",
        
        # Doctors & Specialists
        "doctor", "physician", "surgeon", "dentist", "orthodontist", "ophthalmologist",
        "cardiologist", "neurologist", "pediatrician", "gynecologist", "dermatologist",
        "psychiatrist", "psychologist", "therapist", "counselor",
        
        # Pharmacy & Medicines
        "pharmacy", "medical store", "chemist", "drugstore", "apollo pharmacy",
        "medplus", "wells pharmacy", "pharmeasy", "netmeds", "1mg",
        "medicine", "prescription", "tablets", "capsules", "injection", "vaccine",
        "syrup", "ointment", "cream", "drops", "supplements", "vitamins",
        
        # Tests & Diagnostics
        "lab", "pathology", "diagnostic", "blood test", "urine test", "xray", "scan",
        "mri", "ct scan", "ultrasound", "ecg", "echo", "endoscopy", "colonoscopy",
        
        # Wellness & Fitness
        "gym", "fitness", "yoga", "meditation", "spa", "massage", "salon", "parlor",
        "haircut", "facial", "manicure", "pedicure", "wellness", "therapy"
    ],

    "Education": [
        # Institutions
        "school", "college", "university", "institute", "academy", "coaching",
        "tuition", "training center", "learning center", "educational",
        
        # Fees & Payments
        "school fees", "college fees", "tuition fees", "coaching fees", "exam fees",
        "admission fees", "registration fees", "application fees", "donation",
        "development fees", "transport fees", "hostel fees", "mess fees",
        
        # Materials & Resources
        "books", "stationery", "notebook", "pen", "pencil", "eraser", "sharpener",
        "textbook", "guide", "reference book", "library", "membership",
        
        # Courses & Certifications
        "course", "certification", "diploma", "degree", "online course", "workshop",
        "seminar", "webinar", "conference", "symposium", "training", "skill development",
        
        # Exams & Tests
        "exam", "test", "entrance", "competitive exam", "board exam", "university exam"
    ],

    "Insurance": [
        # Insurance Types
        "insurance", "premium", "policy", "life insurance", "health insurance",
        "car insurance", "bike insurance", "home insurance", "travel insurance",
        "term insurance", "ulip", "endowment", "money back", "child plan",
        "pension plan", "annuity", "medical insurance", "critical illness",
        
        # Insurance Companies
        "lic", "hdfc ergo", "icici lombard", "bajaj allianz", "tata aig",
        "reliance general", "national insurance", "new india", "oriental",
        "united india", "star health", "max bupa", "apollo munich",
        
        # Insurance Terms
        "premium payment", "renewal", "claim", "settlement", "coverage", "sum assured"
    ],

    "Loan_Repayment": [
        # Loan Types
        "loan", "emi", "repayment", "installment", "home loan", "car loan",
        "personal loan", "education loan", "business loan", "gold loan",
        "loan against property", "consumer loan", "vehicle loan",
        
        # Credit Cards
        "credit card", "card payment", "card bill", "credit card dues",
        "minimum amount", "outstanding", "credit limit",
        
        # Banks & Institutions
        "hdfc", "sbi", "icici", "axis", "kotak", "yes bank", "indusind",
        "bank of baroda", "pnb", "canara", "union bank", "idfc", "bandhan",
        
        # Loan Terms
        "principal", "interest", "foreclosure", "prepayment", "part payment",
        "processing fee", "late fee", "penalty", "overdue"
    ],

    "Salary": [
        "salary", "income", "pay", "payroll", "wages", "earnings", "stipend",
        "bonus", "incentive", "commission", "overtime", "allowance",
        "hra", "ta", "da", "conveyance", "medical allowance", "special allowance",
        "arrears", "advance", "reimbursement", "refund", "cashback", "reward",
        "points", "redemption", "dividend", "interest income", "rental income",
        "freelance", "consulting", "professional fees"
    ],

    "Shopping": [
        # Online Retail
        "amazon", "flipkart", "myntra", "nykaa", "ajio", "meesho", "snapdeal",
        "shopclues", "indiamart", "alibaba", "ebay", "etsy", "aliexpress",
        
        # Physical Stores
        "mall", "shopping", "retail", "store", "outlet", "showroom", "boutique",
        "department store", "superstore", "hypermarket",
        
        # Fashion & Apparel
        "clothes", "clothing", "apparel", "garments", "dress", "shirt", "pant",
        "jeans", "t-shirt", "top", "skirt", "kurta", "saree", "salwar", "lehenga",
        "footwear", "shoes", "slippers", "sandals", "heels", "sneakers",
        
        # Electronics & Gadgets
        "electronics", "mobile", "laptop", "computer", "tablet", "camera",
        "headphone", "earphone", "speaker", "tv", "television", "refrigerator",
        "ac", "washing machine", "microwave", "oven", "mixer", "grinder",
        
        # Home & Kitchen
        "furniture", "home decor", "kitchenware", "utensils", "cookware",
        "bedding", "mattress", "curtains", "carpet", "painting", "art",
        
        # Personal Care
        "cosmetics", "makeup", "skincare", "beauty", "perfume", "deodorant",
        "soap", "shampoo", "conditioner", "oil", "lotion", "cream"
    ],

    "Travel": [
        # Flights & Airlines
        "flight", "airline", "indigo", "air india", "spicejet", "vistara",
        "goair", "airasia", "emirates", "qatar", "singapore airlines",
        "flight ticket", "air ticket", "booking",
        
        # Hotels & Accommodation
        "hotel", "booking", "airbnb", "resort", "hostel", "lodging", "inn",
        "motel", "guest house", "service apartment", "vacation rental",
        
        # Railways
        "train", "rail", "irctc", "tatkal", "reservation", "train ticket",
        "railway", "metro", "local",
        
        # Buses & Road Transport
        "bus", "volvo", "sleeper", "bus ticket", "travels", "transport",
        
        # Vacation & Tourism
        "vacation", "holiday", "tour", "tourism", "sightseeing", "package",
        "itinerary", "guide", "tourist", "destination", "beach", "mountain",
        "hill station", "pilgrimage", "religious", "temple", "church", "mosque",
        
        # Travel Accessories
        "luggage", "baggage", "suitcase", "backpack", "travel gear", "passport",
        "visa", "forex", "currency", "travel insurance"
    ],

    "Miscellaneous": [
        "misc", "miscellaneous", "other", "cash", "withdrawal", "deposit",
        "transfer", "gift", "present", "donation", "charity", "contribution",
        "tip", "gratuity", "reward", "cashback", "points", "redemption",
        "refund", "settlement", "payout", "commission", "brokerage",
        "professional fee", "consultation", "service charge", "handling fee",
        "shipping", "delivery", "courier", "post", "logistics", "freight",
        "customs", "duty", "tax", "fine", "penalty", "late fee", "overdue",
        "membership", "subscription", "renewal", "maintenance", "repair",
        "service", "installation", "setup", "configuration"
    ]
}

def categorize(description: str) -> str:
    """
    Categorize a transaction description into a predefined category.
    Manual override can still be applied at the frontend.
    """
    desc = description.lower()
    # 1️⃣ Rule-based: exact or partial match
    for cat, examples in CATEGORY_EXAMPLES.items():
        for ex in examples:
            if ex in desc:
                return cat

    # 2️⃣ NLP similarity fallback
    categories = list(CATEGORY_EXAMPLES.keys())
    example_texts = [" ".join(CATEGORY_EXAMPLES[c]) for c in categories]
    
    try:
        tfidf = TfidfVectorizer().fit(example_texts + [desc])
        vectors = tfidf.transform(example_texts + [desc])
        sim_scores = cosine_similarity(vectors[-1], vectors[:-1])
        best_idx = np.argmax(sim_scores)
        if sim_scores[0, best_idx] > 0.2:  # threshold
            return categories[best_idx]
    except Exception as e:
        pass

    # 3️⃣ Default fallback
    return "Uncategorized"
