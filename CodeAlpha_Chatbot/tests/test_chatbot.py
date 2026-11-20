import json
from pathlib import Path

import pytest

from app import create_app
from chatbot import ChatBot

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def bot():
    return ChatBot(seed=0)


@pytest.fixture()
def client():
    app = create_app(db_path=":memory:")
    app.config["TESTING"] = True
    return app.test_client()


# ---------- model accuracy ----------
def test_held_out_accuracy_is_high(bot):
    eval_set = json.loads((ROOT / "data" / "eval_set.json").read_text(encoding="utf-8"))
    correct = sum(bot.predict(e["text"])[0] == e["intent"] for e in eval_set)
    assert correct / len(eval_set) >= 0.90


def test_every_training_pattern_is_recognised(bot):
    for tag, intent in bot.intents.items():
        for pattern in intent["patterns"]:
            assert bot.predict(pattern)[0] == tag, pattern


@pytest.mark.parametrize("typo,intent", [
    ("waht shuold i eat", "meal_suggestion"),
    ("supprise me", "surprise_me"),
    ("cokking tips", "cooking_tips"),
    ("helthy food", "healthy_eating"),
])
def test_tolerates_typos(bot, typo, intent):
    assert bot.predict(typo)[0] == intent


def test_gibberish_falls_back(bot):
    reply = bot.respond("qwzx plorf vrrmb", "s-gib")
    assert reply.intent == "fallback"
    assert reply.suggestions


def test_response_is_fast(bot):
    bot.respond("warm up", "s-fast")
    assert bot.respond("what should i eat", "s-fast").latency_ms < 100


# ---------- recipe data ----------
def test_recipe_data_is_complete(bot):
    ids = set()
    for r in bot.kitchen.recipes:
        assert r["id"] not in ids
        ids.add(r["id"])
        assert r["ingredients"] and r["steps"] and r["meals"] and r["time"] > 0
        if "vegan" in r["diets"]:
            assert "vegetarian" in r["diets"], r["id"]
        if "vegetarian" in r["diets"]:
            assert not {"chicken"} & set(r["ingredients"]), r["id"]


# ---------- cook with what you have ----------
def test_ingredient_search_ranks_best_match_first(bot):
    reply = bot.respond("I have rice, carrot, peas, onion, garlic, soy sauce and bell pepper", "s-ing")
    assert reply.intent == "ingredient_search"
    assert reply.suggestions[0] == "How to make Vegetable Fried Rice"
    assert "you have everything" in reply.reply


def test_bare_ingredient_list_is_a_search(bot):
    assert bot.respond("eggs, bread, milk", "s-bare").intent == "ingredient_search"


def test_ingredient_flow_uses_context(bot):
    first = bot.respond("what can I cook with what I have", "s-ctx")
    assert first.intent == "cook_with_ingredients"
    second = bot.respond("chicken, lemon, garlic, potatoes", "s-ctx")
    assert second.intent == "ingredient_search"
    assert "Lemon Garlic Chicken" in second.suggestions[0]


def test_synonyms_are_understood(bot):
    have = bot.kitchen.find_ingredients("I have aloo, capsicum, curd and green chillies")
    assert have == {"potato", "bell pepper", "yogurt", "green chili"}


# ---------- suggestions, filters and diet ----------
def test_filters_are_parsed(bot):
    f = bot.kitchen.parse_filters("quick vegetarian indian dinner")
    assert (f.meal, f.diet, f.cuisine, f.max_time) == ("dinner", "vegetarian", "indian", 20)
    assert bot.kitchen.parse_filters("lunch under 15 minutes").max_time == 15


def test_suggestions_respect_filters(bot):
    for _ in range(5):
        reply = bot.respond("quick vegetarian dinner", "s-filter")
        names = [s.removeprefix("How to make ") for s in reply.suggestions if s.startswith("How to make")]
        for name in names:
            r = next(r for r in bot.kitchen.recipes if r["name"] == name)
            assert "vegetarian" in r["diets"] and r["time"] <= 20


def test_diet_preference_is_remembered(bot):
    assert "vegan" in bot.respond("I am vegan", "s-diet").reply
    for _ in range(5):
        for s in bot.respond("what should i eat", "s-diet").suggestions:
            if s.startswith("How to make"):
                r = next(r for r in bot.kitchen.recipes if r["name"] == s.removeprefix("How to make "))
                assert "vegan" in r["diets"]
    assert bot.respond("chicken recipes", "s-diet").intent == "meal_suggestion"
    bot.respond("I eat everything", "s-diet")
    assert "chicken" in bot.respond("chicken recipes", "s-diet").reply.lower()


def test_diet_is_per_session(bot):
    bot.respond("I am vegan", "s-a")
    assert "Showing vegan" not in bot.respond("what should i eat", "s-b").reply


# ---------- recipes, substitutes, plans ----------
def test_full_recipe_by_name(bot):
    reply = bot.respond("how do I make shakshuka?", "s-recipe")
    assert reply.intent == "recipe_detail"
    assert "Steps" in reply.reply and "1." in reply.reply


def test_substitution(bot):
    reply = bot.respond("I don't have eggs, what can I use instead?", "s-sub")
    assert reply.intent == "substitution" and "banana" in reply.reply


def test_substitution_asks_then_answers(bot):
    assert "Which ingredient" in bot.respond("I need a substitute", "s-sub2").reply
    assert "oil" in bot.respond("butter", "s-sub2").reply


def test_meal_plan_has_three_meals(bot):
    reply = bot.respond("plan my meals today", "s-plan")
    assert all(m in reply.reply for m in ("Breakfast", "Lunch", "Dinner"))


def test_every_suggestion_chip_gets_an_answer(bot):
    chips = {s for i in bot.intents.values() for s in i.get("suggestions", [])}
    chips |= {"Something else", "Another plan", "Ingredient substitutes", "Surprise me again", "Another tip"}
    for chip in chips:
        assert bot.respond(chip, f"chip-{chip}").intent != "fallback", chip


# ---------- HTTP API ----------
def test_chat_endpoint(client):
    res = client.post("/api/chat", json={"message": "hello", "session_id": "t1"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["intent"] == "greeting"
    assert data["reply"] and data["message_id"] > 0
    assert res.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "   "}, {"message": 42}, {"message": "x" * 501}])
def test_chat_rejects_bad_input(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 400


def test_feedback_and_stats(client):
    msg = client.post("/api/chat", json={"message": "surprise me", "session_id": "t2"}).get_json()
    client.post("/api/chat", json={"message": "blorp zzz", "session_id": "t2"})
    assert client.post("/api/feedback", json={"message_id": msg["message_id"], "helpful": True}).status_code == 200
    assert client.post("/api/feedback", json={"message_id": 9999, "helpful": True}).status_code == 404
    assert client.post("/api/feedback", json={"message_id": "1", "helpful": "yes"}).status_code == 400

    stats = client.get("/api/stats").get_json()
    assert stats["total_messages"] == 2
    assert stats["answer_rate"] == 0.5
    assert stats["feedback"]["helpful"] == 1
    assert stats["unanswered"][0]["user_text"] == "blorp zzz"


def test_pages_render(client):
    home = client.get("/").data.decode()
    assert "widget.js" in home and "FoodieBot" in home and "Masala Omelette" in home
    assert client.get("/dashboard").status_code == 200
    assert client.get("/static/widget.js").status_code == 200
    assert client.get("/health").get_json()["status"] == "ok"
