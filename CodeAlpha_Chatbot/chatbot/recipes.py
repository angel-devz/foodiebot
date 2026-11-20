"""Recipe knowledge base: ingredient detection, filtering, ranking and substitutes."""
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from .nlp import normalize

RECIPES_PATH = Path(__file__).resolve().parent.parent / "data" / "recipes.json"

# user word -> canonical ingredient name used in recipes.json
SYNONYMS = {
    "eggs": "egg", "anda": "egg", "tomatoes": "tomato", "tamatar": "tomato", "potatoes": "potato", "aloo": "potato",
    "onions": "onion", "pyaz": "onion", "chilli": "green chili", "chillies": "green chili", "chili": "green chili",
    "chilies": "green chili", "green chilli": "green chili", "green chillies": "green chili", "green chilies": "green chili",
    "cilantro": "coriander", "dhania": "coriander", "capsicum": "bell pepper", "bell peppers": "bell pepper",
    "peppers": "bell pepper", "curd": "yogurt", "yoghurt": "yogurt", "dahi": "yogurt", "garbanzo": "chickpeas",
    "chickpea": "chickpeas", "chana": "chickpeas", "chole": "chickpeas", "dal": "lentils", "daal": "lentils",
    "lentil": "lentils", "spaghetti": "pasta", "penne": "pasta", "macaroni": "pasta", "tortillas": "tortilla",
    "wraps": "tortilla", "wrap": "tortilla", "kidney beans": "beans", "black beans": "beans", "rajma": "beans",
    "maida": "flour", "all purpose flour": "flour", "atta": "flour", "noodle": "noodles", "ramen": "noodles",
    "basmati": "rice", "chawal": "rice", "peanuts": "peanut", "groundnuts": "peanut", "groundnut": "peanut",
    "curry leaf": "curry leaves", "cocoa powder": "cocoa", "chocolate": "cocoa", "limes": "lime", "lemons": "lemon",
    "carrots": "carrot", "bananas": "banana", "mangoes": "mango", "mangos": "mango", "avocados": "avocado",
    "cucumbers": "cucumber", "olive": "olives", "chicken breast": "chicken", "breads": "bread", "toast": "bread",
    "pav": "bread", "green peas": "peas", "matar": "peas", "sweetcorn": "corn", "sweet corn": "corn",
    "jeera": "cumin", "cumin seeds": "cumin", "chili flake": "chili flakes", "red chili flakes": "chili flakes",
    "oat": "oats", "oatmeal": "oats", "ghee": "butter", "cottage cheese": "paneer", "fresh cream": "cream",
    "heavy cream": "cream", "brocolli": "broccoli", "garlic cloves": "garlic", "lahsun": "garlic", "adrak": "ginger",
}

# Having a general ingredient covers its specific forms.
COVERS = {"cheese": {"mozzarella", "feta"}, "oil": {"olive oil"}, "lemon": {"lime"}, "lime": {"lemon"}}

SUBSTITUTES = {
    "egg": "1 egg = 3 tbsp mashed banana, 3 tbsp yogurt, or 1 tbsp ground flaxseed + 3 tbsp water (rest 5 min). For omelettes, try a besan (chickpea flour) batter.",
    "butter": "Use the same amount of oil or ghee for cooking; for baking use ¾ the amount of oil, or mashed banana.",
    "milk": "Use any plant milk (oat, soy, almond), or ½ water + ½ yogurt for baking.",
    "cream": "Mix ¾ cup milk + ¼ cup melted butter, or blend soaked cashews with water. Thick yogurt also works in curries (add off the heat).",
    "yogurt": "Use sour cream, buttermilk, or milk + 1 tsp lemon juice (let it sit 5 minutes).",
    "sugar": "Use honey or maple syrup (¾ the amount, and reduce other liquid slightly), or jaggery.",
    "flour": "For thickening use cornstarch (half the amount). For baking try oat flour (blend oats).",
    "soy sauce": "Use a pinch of salt + a few drops of vinegar, or Worcestershire sauce.",
    "lemon": "Use lime juice, or vinegar (half the amount).",
    "lime": "Use lemon juice — it works the same way.",
    "garlic": "Use ⅛ tsp garlic powder per clove, or skip it and add a little extra onion.",
    "onion": "Use shallots or spring onions, or ¼ tsp onion powder per small onion.",
    "honey": "Use maple syrup, sugar syrup or jaggery.",
    "paneer": "Use tofu (press it first), or boiled chickpeas.",
    "chicken": "Use paneer, tofu, chickpeas or mushrooms — cook vegetables for less time.",
    "cheese": "Use nutritional yeast for a cheesy flavour, or a thick white sauce.",
    "rice": "Use quinoa, couscous, broken wheat (dalia) or cauliflower rice.",
    "pasta": "Use noodles, or spiralised zucchini for a low-carb version.",
    "tomato": "Use 1 tbsp tomato paste/ketchup + water per tomato, or canned tomatoes.",
    "baking powder": "Use ¼ tsp baking soda + ½ tsp lemon juice or vinegar per 1 tsp baking powder.",
    "bread": "Use tortillas, rotis or crackers.",
    "coconut milk": "Use milk/cream with a little desiccated coconut, or cashew cream.",
    "tahini": "Use peanut butter or sesame oil.",
    "peanut butter": "Use any nut butter, or tahini.",
    "coriander": "Use parsley or mint.",
    "basil": "Use parsley, spinach or a pinch of dried oregano.",
}

MEAL_WORDS = {
    "breakfast": "breakfast", "brunch": "breakfast", "morning": "breakfast", "lunch": "lunch",
    "dinner": "dinner", "supper": "dinner", "tonight": "dinner", "dessert": "dessert", "sweet": "dessert",
    "snack": "snack", "snacks": "snack", "starter": "snack",
}
CUISINE_WORDS = {
    "indian": "indian", "italian": "italian", "mexican": "mexican", "chinese": "chinese", "thai": "thai",
    "mediterranean": "mediterranean", "greek": "mediterranean", "american": "american",
}
NUMBER_WORDS = {"five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}


@dataclass
class Filters:
    meal: str | None = None
    diet: str | None = None          # vegetarian / vegan / gluten_free
    max_time: int | None = None
    cuisine: str | None = None
    healthy: bool = False
    include: set[str] = field(default_factory=set)

    def describe(self) -> str:
        parts = []
        if self.healthy:
            parts.append("healthy")
        if self.max_time:
            parts.append(f"under {self.max_time} min")
        if self.diet:
            parts.append(self.diet.replace("_", "-"))
        if self.cuisine:
            parts.append(self.cuisine.title())
        if self.meal:
            parts.append(self.meal)
        if self.include:
            parts.append("with " + ", ".join(sorted(self.include)))
        return " ".join(parts)


def detect_diet(text: str) -> str | None:
    t = normalize(text)
    if re.search(r"\bnon ?veg|\beat (meat|everything|non)|\bnot vegetarian\b|\bremove\b", t):
        return "none"
    if "vegan" in t:
        return "vegan"
    if re.search(r"\bgluten\b", t):
        return "gluten_free"
    if re.search(r"\b(vegetarian|veg|veggie|meatless|no meat|pure veg|don't eat meat|do not eat meat)\b", t):
        return "vegetarian"
    return None


class Kitchen:
    def __init__(self, path: Path = RECIPES_PATH, seed: int | None = None):
        with open(path, encoding="utf-8") as f:
            self.recipes: list[dict] = json.load(f)
        self.by_id = {r["id"]: r for r in self.recipes}
        self.rng = random.Random(seed)

        vocab = {i for r in self.recipes for i in r["ingredients"] + r["pantry"]}
        self.vocab = {v: v for v in vocab}
        for v in vocab:
            self.vocab.setdefault(v + "s", v)
            self.vocab.setdefault(v + "es", v)
        self.vocab.update(SYNONYMS)
        self.vocab.update({k: k for k in SUBSTITUTES})
        # longest phrases first so "green chili" wins over "chili"
        self._vocab_terms = sorted(self.vocab, key=len, reverse=True)

        aliases = [(normalize(a), r["id"]) for r in self.recipes for a in r["aliases"] + [r["name"]]]
        self._aliases = sorted(set(aliases), key=lambda a: len(a[0]), reverse=True)

    # ---------- detection ----------
    def find_ingredients(self, text: str) -> set[str]:
        padded = f" {normalize(text)} "
        found = set()
        for term in self._vocab_terms:
            needle = f" {term} "
            if needle in padded:
                found.add(self.vocab[term])
                padded = padded.replace(needle, "  ")
        return found

    def find_recipe(self, text: str) -> dict | None:
        padded = f" {normalize(text)} "
        for alias, rid in self._aliases:
            if f" {alias} " in padded:
                return self.by_id[rid]
        return None

    def parse_filters(self, text: str, diet: str | None = None) -> Filters:
        t = normalize(text)
        words = t.split()
        f = Filters(diet=diet)
        for w in words:
            if w in MEAL_WORDS and not f.meal:
                f.meal = MEAL_WORDS[w]
            if w in CUISINE_WORDS and not f.cuisine:
                f.cuisine = CUISINE_WORDS[w]
        found = detect_diet(t)
        if found and found != "none":
            f.diet = found
        m = re.search(r"\b(\d{1,3}|five|ten|fifteen|twenty|thirty)\s*(min|mins|minute|minutes)\b", t)
        if m:
            f.max_time = int(NUMBER_WORDS.get(m.group(1), m.group(1)))
        elif re.search(r"\b(quick|quickly|fast|easy|lazy|hurry|instant)\b", t):
            f.max_time = 20
        f.healthy = bool(re.search(r"\b(healthy|light|low calorie|diet|nutritious|protein)\b", t))
        f.include = {i for i in self.find_ingredients(t) if any(i in r["ingredients"] for r in self.recipes)}
        return f

    # ---------- search ----------
    @staticmethod
    def _diet_ok(recipe: dict, diet: str | None) -> bool:
        return not diet or diet in recipe["diets"]

    def matches(self, recipe: dict, f: Filters) -> bool:
        return (
            self._diet_ok(recipe, f.diet)
            and (not f.meal or f.meal in recipe["meals"])
            and (not f.cuisine or recipe["cuisine"] == f.cuisine)
            and (not f.max_time or recipe["time"] <= f.max_time)
            and (not f.healthy or recipe["healthy"])
            and f.include.issubset(recipe["ingredients"])
        )

    def suggest(self, f: Filters, k: int = 3) -> tuple[list[dict], bool]:
        """Return up to k recipes and whether the filters had to be relaxed."""
        pool = [r for r in self.recipes if self.matches(r, f)]
        relaxed = False
        if not pool:  # keep the diet (a hard constraint), relax the rest
            relaxed = True
            pool = [r for r in self.recipes if self._diet_ok(r, f.diet)
                    and (not f.include or f.include & set(r["ingredients"]))]
        return self.rng.sample(pool, min(k, len(pool))), relaxed

    def by_ingredients(self, have: set[str], diet: str | None = None, k: int = 3) -> list[dict]:
        """Rank recipes by how many of their ingredients the user already has."""
        have = set(have)
        for item in list(have):
            have |= COVERS.get(item, set())
        ranked = []
        for r in self.recipes:
            if not self._diet_ok(r, diet):
                continue
            need = set(r["ingredients"])
            got = need & have
            if not got:
                continue
            ranked.append({"recipe": r, "have": sorted(got), "missing": sorted(need - have),
                           "score": len(got) / len(need)})
        ranked.sort(key=lambda m: (-m["score"], len(m["missing"]), -len(m["have"]), m["recipe"]["time"]))
        return ranked[:k]

    def random(self, diet: str | None = None) -> dict:
        return self.rng.choice([r for r in self.recipes if self._diet_ok(r, diet)])

    def substitutes_for(self, text: str) -> list[tuple[str, str]]:
        return [(i, SUBSTITUTES[i]) for i in sorted(self.find_ingredients(text)) if i in SUBSTITUTES]

    # ---------- formatting ----------
    @staticmethod
    def badge(r: dict) -> str:
        diet = "vegan" if "vegan" in r["diets"] else "veg" if "vegetarian" in r["diets"] else "non-veg"
        return f"⏱ {r['time']} min · {diet} · {r['calories']} kcal"

    @staticmethod
    def card(r: dict) -> str:
        lines = [
            f"{r['emoji']} **{r['name']}**",
            f"⏱ {r['time']} min · 🍽 serves {r['servings']} · {r['difficulty']} · 🔥 {r['calories']} kcal/serving",
            "",
            "**Ingredients:** " + ", ".join(r["ingredients"]),
        ]
        if r["pantry"]:
            lines.append("**Pantry:** " + ", ".join(r["pantry"]))
        lines += ["", "**Steps:**"] + [f"{n}. {s}" for n, s in enumerate(r["steps"], 1)]
        return "\n".join(lines)
