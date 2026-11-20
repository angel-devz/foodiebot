"""FoodieBot response engine.

For each message:
  1. Conversation context  - e.g. after "cook with what I have" the next message is read as ingredients.
  2. Intent classification - TF-IDF + Logistic Regression model (see model.py).
  3. Entity detection      - recipe names, ingredients, meal type, diet, cooking time, cuisine.
  4. Action                - search the recipe book (ingredient match, filtered suggestions,
                             full recipe, substitutes, meal plan) or return a curated answer.
  5. Fallback              - below the confidence threshold the bot asks the user to rephrase.
"""
import random
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace

from .model import load_intents, load_or_train
from .nlp import normalize
from .recipes import Filters, Kitchen, detect_diet

FALLBACK_RESPONSES = [
    "Hmm, I didn't quite get that 🤔. Try \"I have eggs and tomatoes\", \"quick vegetarian dinner\" or \"how to make pancakes\".",
    "Sorry, I'm not sure what you mean. You can tell me your ingredients, ask what to eat, or ask for a recipe by name.",
]
FALLBACK_SUGGESTIONS = ["What can you do?", "Cook with what I have", "Surprise me"]
SWAP_CUES = re.compile(
    r"\b(instead|substitut\w*|replac\w*|swap\w*|alternative\w*|do not have|no|out of|ran out|missing|without)\b"
)
DIET_LABEL = {"vegetarian": "vegetarian 🥦", "vegan": "vegan 🌱", "gluten_free": "gluten-free 🌾"}


@dataclass
class Reply:
    reply: str
    intent: str
    confidence: float
    suggestions: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "suggestions": self.suggestions,
            "latency_ms": round(self.latency_ms, 2),
        }


def how_to(recipes: list[dict]) -> list[str]:
    return [f"How to make {r['name']}" for r in recipes]


class ChatBot:
    def __init__(self, threshold: float = 0.30, seed: int | None = None):
        self.threshold = threshold
        self.data = load_intents()
        self.intents = {i["tag"]: i for i in self.data["intents"]}
        self.model = load_or_train()
        self.kitchen = Kitchen(seed=seed)
        self.exact = {normalize(p): i["tag"] for i in self.data["intents"] for p in i["patterns"]}
        self.sessions: dict[str, dict] = defaultdict(dict)  # session_id -> {context, diet, last_filters}
        self.rng = random.Random(seed)

    # ----- public API -------------------------------------------------
    def predict(self, text: str) -> tuple[str, float]:
        clean = normalize(text)
        if not clean:
            return "fallback", 0.0
        if clean in self.exact:
            return self.exact[clean], 1.0
        probs = self.model.predict_proba([clean])[0]
        best = probs.argmax()
        return self.model.classes_[best], float(probs[best])

    def respond(self, message: str, session_id: str = "default") -> Reply:
        start = time.perf_counter()
        reply = self._respond(message.strip(), self.sessions[session_id])
        reply.latency_ms = (time.perf_counter() - start) * 1000
        return reply

    # ----- routing ----------------------------------------------------
    def _respond(self, message: str, state: dict) -> Reply:
        if not message:
            return Reply("Please type a message 🙂", "empty", 0.0, FALLBACK_SUGGESTIONS)

        k = self.kitchen
        pending = state.pop("context", None)
        ingredients = k.find_ingredients(message)

        if pending == "awaiting_ingredients" and ingredients:
            return self._ingredient_search(ingredients, state, 1.0)
        if pending == "awaiting_substitute" and k.substitutes_for(message):
            return self._substitute(message, state, 1.0)

        tag, conf = self.predict(message)
        confident = conf >= self.threshold

        # A bare list of ingredients ("eggs, bread, milk") is a search, not a swap request.
        is_swap = SWAP_CUES.search(normalize(message)) or len(ingredients) <= 1
        if confident and tag == "substitution" and is_swap:
            return self._substitute(message, state, conf)
        if confident and tag == "set_diet":
            return self._set_diet(message, state, conf)

        recipe = k.find_recipe(message)
        if recipe:
            return Reply(k.card(recipe), "recipe_detail", 1.0,
                         ["Ingredient substitutes", "What should I eat?", "Surprise me"])

        cooking_items = {i for i in ingredients if any(i in r["ingredients"] for r in k.recipes)}
        if (tag in {"cook_with_ingredients", "substitution"} and cooking_items) or (
            len(cooking_items) >= 2 and tag not in {"meal_suggestion", "healthy_eating"}
        ) or (not confident and cooking_items):
            return self._ingredient_search(cooking_items, state, max(conf, 0.5))

        if not confident or tag not in self.intents:
            return Reply(self.rng.choice(FALLBACK_RESPONSES), "fallback", conf, FALLBACK_SUGGESTIONS)

        intent = self.intents[tag]
        action = intent.get("action")
        if action == "suggest":
            return self._suggest(message, state, conf)
        if action == "surprise":
            r = k.random(state.get("diet"))
            return Reply(f"{intent['responses'][0]}\n\n{k.card(r)}", tag, conf, ["Surprise me again", "What should I eat?"])
        if action == "healthy":
            return self._healthy(message, state, conf)
        if action == "meal_plan":
            return self._meal_plan(state, conf)
        if action == "list":
            return self._list(conf)
        if action == "substitute":
            return self._substitute(message, state, conf)

        if intent.get("context_set"):
            state["context"] = intent["context_set"]
        return Reply(self.rng.choice(intent["responses"]), tag, conf, intent.get("suggestions", []))

    # ----- actions ----------------------------------------------------
    def _diet_note(self, state: dict) -> str:
        diet = state.get("diet")
        return f"\n\n(Showing {DIET_LABEL[diet].split()[0]} recipes only — say \"I eat everything\" to change.)" if diet else ""

    def _ingredient_search(self, have: set[str], state: dict, conf: float) -> Reply:
        matches = self.kitchen.by_ingredients(have, state.get("diet"))
        if not matches:
            state["context"] = "awaiting_ingredients"
            return Reply(
                f"I couldn't find a recipe using {', '.join(sorted(have))} 😕. Try adding a few more ingredients "
                "— onion, tomato, eggs, rice or bread open up lots of options!",
                "ingredient_search", conf, ["eggs, onion, tomato", "Surprise me"],
            )
        lines = [f"🥕 With **{', '.join(sorted(have))}** you can make:", ""]
        for n, m in enumerate(matches, 1):
            r = m["recipe"]
            need = len(m["have"]) + len(m["missing"])
            status = "✅ you have everything!" if not m["missing"] else f"missing: {', '.join(m['missing'])}"
            lines.append(f"{n}. {r['emoji']} **{r['name']}** — {len(m['have'])}/{need} ingredients, {status}")
            lines.append(f"    {self.kitchen.badge(r)}")
        lines.append("\nTap a dish to see the full recipe 👇")
        recipes = [m["recipe"] for m in matches]
        return Reply("\n".join(lines) + self._diet_note(state), "ingredient_search", conf, how_to(recipes))

    def _suggest(self, message: str, state: dict, conf: float) -> Reply:
        f = self.kitchen.parse_filters(message, state.get("diet"))
        if f.describe() == Filters(diet=f.diet).describe() and state.get("last_filters"):
            # "something else" -> same filters, new picks (keeping any newer diet preference)
            f = replace(state["last_filters"], diet=state.get("diet") or state["last_filters"].diet)
        state["last_filters"] = f
        picks, relaxed = self.kitchen.suggest(f)
        label = f.describe()
        if not picks:
            state.pop("last_filters", None)
            return Reply(f"I don't have any {label} recipes yet 😕. Try different ingredients or another meal.",
                         "meal_suggestion", conf, ["What should I eat?", "Cook with what I have"])
        head = (f"I don't have an exact match for \"{label}\", but you might like these:" if relaxed
                else f"🍽️ Some ideas ({label}):" if label else "🍽️ How about one of these?")
        lines = [head, ""] + [f"{r['emoji']} **{r['name']}** — {self.kitchen.badge(r)}" for r in picks]
        return Reply("\n".join(lines) + self._diet_note(state), "meal_suggestion", conf,
                     how_to(picks) + ["Something else"])

    def _healthy(self, message: str, state: dict, conf: float) -> Reply:
        f = self.kitchen.parse_filters(message, state.get("diet"))
        f.healthy = True
        picks, _ = self.kitchen.suggest(f)
        lines = [self.intents["healthy_eating"]["responses"][0], ""]
        lines += [f"{r['emoji']} **{r['name']}** — {self.kitchen.badge(r)}" for r in picks]
        lines.append("\n💡 Fill half your plate with vegetables, choose whole grains and drink plenty of water.")
        return Reply("\n".join(lines) + self._diet_note(state), "healthy_eating", conf, how_to(picks))

    def _meal_plan(self, state: dict, conf: float) -> Reply:
        diet = state.get("diet")
        plan, used = [], set()
        for meal in ("breakfast", "lunch", "dinner"):
            options = [r for r in self.kitchen.recipes
                       if meal in r["meals"] and (not diet or diet in r["diets"]) and r["id"] not in used]
            pick = self.rng.choice(options)
            used.add(pick["id"])
            plan.append((meal, pick))
        total = sum(r["calories"] for _, r in plan)
        lines = [self.intents["meal_plan"]["responses"][0], ""]
        lines += [f"**{meal.title()}:** {r['emoji']} {r['name']} ({r['time']} min, {r['calories']} kcal)" for meal, r in plan]
        lines.append(f"\n🔥 Total: about {total} kcal (per serving). Add fruit or yogurt as snacks.")
        return Reply("\n".join(lines) + self._diet_note(state), "meal_plan", conf,
                     how_to([r for _, r in plan]) + ["Another plan"])

    def _list(self, conf: float) -> Reply:
        by_cuisine: dict[str, list[str]] = defaultdict(list)
        for r in self.kitchen.recipes:
            by_cuisine[r["cuisine"]].append(r["name"])
        lines = [f"📖 My recipe book has {len(self.kitchen.recipes)} recipes:", ""]
        lines += [f"**{c.title()}:** {', '.join(sorted(names))}" for c, names in sorted(by_cuisine.items())]
        lines.append("\nAsk \"how to make …\" for any of them!")
        return Reply("\n".join(lines), "list_recipes", conf, ["Surprise me", "Cook with what I have"])

    def _substitute(self, message: str, state: dict, conf: float) -> Reply:
        subs = self.kitchen.substitutes_for(message)
        if not subs:
            state["context"] = "awaiting_substitute"
            intent = self.intents["substitution"]
            return Reply(intent["responses"][0], "substitution", conf, intent["suggestions"])
        lines = ["🔄 Ingredient swaps:", ""] + [f"**{name.title()}:** {tip}" for name, tip in subs]
        return Reply("\n".join(lines), "substitution", conf, ["Cook with what I have", "Surprise me"])

    def _set_diet(self, message: str, state: dict, conf: float) -> Reply:
        diet = detect_diet(message)
        if diet in DIET_LABEL:
            state["diet"] = diet
            return Reply(f"Got it! I'll only suggest {DIET_LABEL[diet]} recipes from now on.", "set_diet", conf,
                         ["What should I eat?", "Plan my meals today"])
        state.pop("diet", None)
        return Reply("No problem — I'll suggest recipes of every kind again 🍗🥦.", "set_diet", conf,
                     ["What should I eat?", "Surprise me"])
