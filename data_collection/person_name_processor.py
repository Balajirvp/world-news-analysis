import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class SemanticNameDeduplicator:
    """Semantic similarity-based name deduplication for person names."""

    def __init__(self, model_name='all-MiniLM-L6-v2', similarity_threshold=0.9):
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = similarity_threshold
        # Canonical names mapping (expand as needed)
        self.canonical_names = {
            "Donald Trump": ["trump", "donald trump", "' trump", '" trump"', "' trump"],
            "Volodymyr Zelenskyy": ["zelensky", "zelenskyy", "zele", "zelenski", "zelenskiy", "volodymyr zelenskyy", "volodymyr zelensky", "— zelenskyy", "##nsky"],
            "Vladimir Putin": ["putin", "vladimir putin", "' putin"],
            "Benjamin Netanyahu": ["netanyahu", "benjamin netanyahu"],
            "Yair Netanyahu": ["yair netanyahu"],
            "Narendra Modi": ["modi", "' modi"],
            "Keir Starmer": ["starmer", "keir starmer"],
            "Marco Rubio": ["rubio", "marco rubio"],
            "Mark Carney": ["carney", "mark carney"],
            "Friedrich Merz": ["merz", "friedrich merz", "me"],
            "Xi Jinping": ["xi", "xi jinping"],
            "JD Vance": ["vance", "jd vance"],
            "Pete Hegseth": ["hegseth", "pete hegseth"],
            "Anthony Albanese": ["albanese", "anthony albanese"],
            "Giorgia Meloni": ["meloni", "giorgia meloni"],
            "Kim Jong Un": ["kim jong un", "kim jong", "kim", "un"],
            "Emmanuel Macron": ["macron", "emmanuel macron"],
            "Elon Musk": ["musk", "elon musk"],
            "Pope Francis": ["pope", "pope francis", "francis"],
            "Pope Leo XIV": ["pope leo xiv", "pope leo", "leo xiv"],
            "Ursula Von Der Leyen": ["von der leyen", "von der leye", "von der le"],
            "Pierre Poilievre": ["poilievre", "pierre poilievre"],
            "Claudia Sheinbaum": ["sheinbaum", "claudia sheinbaum"],
            "Donald Tusk": ["tusk", "donald tusk"],
            "King Charles III": ["charles", "charles iii", "king charles", "king"],
            "Viktor Orban": ["orbán", "viktor orban", "orban"],
            "Recep Erdogan": ["erdogan", "erdoğan"],
            "Subrahmanyam Jaishankar": ["jaishankar", "s jaishankar"],
            "Moon Jae-In": ["moon jae", "moon"],
            "Yoon Suk Yeol": ["yoon suk yeol"],
            "Muhammad Yunus": ["yunus", "muhammad yunus"],
            "Sergey Lavrov": ["lavrov"],
            "Olaf Scholz": ["scholz"],
            "Justin Trudeau": ["trudeau"],
            "Javier Milei": ["milei", "mile"],
            "Bashar Al-Assad": ["assad"],
            "Joe Biden": ["biden"],
            "Kaja Kallas": ["kallas"],
            "Luiz Lula Da Silva": ["lula", "lula u"],
            "Ramzan Kadyrov": ["kadyrov"],
            "Shehbaz Sharif": ["shehbaz", "shehbaz sharif"],
            "Camilla": ["camilla"],
            "Asim Munir": ["asim munir", "munir"],
            "Edan Alexander": ["edan alexander"],
            "Mohammed Sinwar": ["mohammed sinwar", "muhammad sinwar"],
            "Abbas": ["abbas"],
            "Hafez Assad": ["assad"],
            "Mahama": ["mahama"],
            "Daniel Andrews": ["andrews"],
            "Ishiba": ["ishiba"],
            "Ahmad Al-Sharaa": ["ahmed al-sharaa", "sharaa", "al-sharaa"],
            "Yurii Ihnat": ["yurii ihnat"],
            "Dmytro Kuleba": ["kuleba"],
            "Rustem Umerov": ["umerov"],
            "Mark Rutte": ["rutte"],
            "Christine Lagarde": ["lagarde"],
            "Jerome Powell": ["powell"],
            "Klaus Schwab": ["klaus schwab"],
            "Bill Gates": ["bill gates"],
            "Lady Gaga": ["lady gaga", "gaga"],
            "Dmitry Medvedev": ["medvedev"],
            "Sergey Shoigu": ["shoigu"],
            "Andres Manuel Lopez Obrador": ["amlo"],
            "Liz Truss": ["truss"],
            "Rishi Sunak": ["sunak"],
            "Fumio Kishida": ["kishida"],
            "Park Geun-Hye": ["park"],
            "Lai Ching-Te": ["lai"],
            "Tsai Ing-Wen": ["tsai ing"],
            "Lee Jae-Myung": ["lee jae", "myung"],
            "William Ruto": ["ruto"],
            "Cyril Ramaphosa": ["ramaphosa"],
            "Nayib Bukele": ["bukele"],
            "Gabriel Boric": ["boric"],
            "Luis Arce": ["arce"],
            "Evo Morales": ["morales"],
            "Jair Bolsonaro": ["bolsonaro"],
            "Dilma Rousseff": ["dilma rousseff"],
            "Fernando Collor": ["collor"],
            "Andrzej Duda": ["duda"],
            "Mateusz Morawiecki": ["morawiecki"],
            "Rafal Trzaskowski": ["trzaskowski"],
            "Karol Nawrocki": ["nawrocki"],
            "Robert Fico": ["fico"],
            "Petr Pavel": ["pavel"],
            "Andrej Babis": ["babis"],
            "Alexander Lukashenko": ["lukashenko"]
        }
        self.name_to_canonical = {}
        for canonical, variations in self.canonical_names.items():
            for variation in variations:
                self.name_to_canonical[self.clean_name(variation)] = canonical

    def clean_name(self, name):
        if not name or pd.isna(name):
            return ""
        cleaned = str(name).strip().lower()
        cleaned = cleaned.replace("'", "").replace('"', "").replace("—", "").replace("#", "").replace("-", "")
        cleaned = " ".join(cleaned.split())
        return cleaned

    def get_embeddings(self, names):
        cleaned_names = [self.clean_name(name) for name in names]
        return self.model.encode(cleaned_names)

    def get_canonical_name(self, name):
        cleaned = self.clean_name(name)
        if cleaned in self.name_to_canonical:
            return self.name_to_canonical[cleaned]
        return name.title()

    def deduplicate(self, names):
        # First pass: canonical mapping
        mapped = [self.get_canonical_name(name) for name in names]
        unique_names = list(set(mapped))
        if len(unique_names) <= 1:
            return unique_names

        # Second pass: semantic similarity grouping
        embeddings = self.get_embeddings(unique_names)
        sim_matrix = cosine_similarity(embeddings)
        groups = []
        used = set()
        for i, name in enumerate(unique_names):
            if i in used:
                continue
            group = [name]
            for j in range(i + 1, len(unique_names)):
                if sim_matrix[i][j] >= self.similarity_threshold:
                    group.append(unique_names[j])
                    used.add(j)
            used.add(i)
            groups.append(group)
        # Choose canonical for each group
        canonical_names = [self.get_canonical_name(group[0]) for group in groups]
        return canonical_names

    def update_persons_mentioned(self, posts):
        for post in posts:
            persons = post.get("persons_mentioned", [])
            if persons:
                updated = self.deduplicate(persons)
                post["persons_mentioned_updated"] = updated
            else:
                post["persons_mentioned_updated"] = []
        return posts