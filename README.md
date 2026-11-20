# CodeAlpha_Chatbot — 👩‍🍳 FoodieBot

**CodeAlpha Cloud Computing Internship — Task 4: Making a Chatbot**

🌐 **Live demo:** https://foodiebot-9i7c.onrender.com · 📊 [Analytics dashboard](https://foodiebot-9i7c.onrender.com/dashboard)

> Hosted on Render's free plan: the first visit after a quiet period may take ~40 seconds while the server wakes up.

**FoodieBot** is an intelligent chatbot that helps users **decide what to eat**, **discover recipes** and **prepare delicious meals using ingredients they already have at home**.

It is a retrieval-based AI chatbot: a machine-learning model works out what the user wants, and a recipe search engine finds the best answer from a book of 31 recipes. It plugs into any website with **one line of HTML**, answers instantly, learns your diet, logs every conversation for analytics, and ships as a Docker container ready for cloud deployment.

---

## 💬 What you can ask

| You say | FoodieBot does |
|---|---|
| *"I have eggs, onion and tomato"* | Ranks recipes by how many of your ingredients they use, and lists what's missing |
| *"What should I eat?"* / *"quick vegetarian dinner"* / *"Indian lunch under 30 minutes"* | Suggests dishes filtered by **meal, diet, cooking time and cuisine** |
| *"How to make pancakes"* | Full recipe: time, servings, calories, ingredients and numbered steps |
| *"I don't have eggs, what can I use?"* | Ingredient substitutes |
| *"I'm vegan"* | Remembers your diet for every later suggestion |
| *"Surprise me"* | A random recipe |
| *"Plan my meals today"* | Breakfast, lunch and dinner plan with total calories |
| *"Something healthy"* / *"cooking tips"* / *"show all recipes"* | Healthy picks, kitchen tips, the full recipe book |

It understands typos (*"waht shuold i eat"*), Indian ingredient names (*aloo, dahi, capsicum, chana*) and follow-ups (*"something else"*).

---

## ✅ How the task requirements are met

| Requirement | Implementation |
|---|---|
| AI-powered chatbot (retrieval-based or generative) | **Retrieval-based**: an ML intent classifier (TF-IDF word + character n-grams → Logistic Regression) plus entity extraction (ingredients, recipe names, meal, diet, time, cuisine) and retrieval from a recipe knowledge base |
| Instant responses on websites | REST API `/api/chat`; replies are generated in a few milliseconds |
| Trained with predefined input patterns for commercial use | `data/intents.json`: 15 intents, 243 training patterns. `data/recipes.json`: 31 recipes across 7 cuisines |
| Seamless integration with the website | `static/widget.js`: a self-contained chat widget added with one `<script>` tag. The FoodieBot website at `/` has an ingredient picker and recipe cards that talk to the bot |
| Optimised and tested for accuracy and engagement | **100% accuracy** on a held-out set of 36 unseen phrasings, typo tolerance, a confidence threshold with a fallback answer, **30 automated tests**, quick-reply chips, 👍/👎 feedback and an analytics dashboard at `/dashboard` |

---

## 🏗️ How it works

```
 User on the website
      │  widget.js (1-line embed)
      ▼
 ┌─────────────────────────── Flask app (gunicorn, Docker) ───────────────────────────┐
 │ POST /api/chat ─► ChatBot.respond()                                                │
 │    1. Context      — was the bot waiting for ingredients / a substitute?           │
 │    2. Intent       — TF-IDF + Logistic Regression ─► intent + confidence           │
 │    3. Entities     — ingredients (with synonyms), recipe name, meal, diet,         │
 │                      cooking time, cuisine                                         │
 │    4. Retrieval    — Kitchen: rank recipes by ingredient match, filter, plan,      │
 │                      substitutes                                                   │
 │    5. Fallback     — confidence < threshold ─► "please rephrase" + suggestions     │
 │ ─► ChatStore (SQLite) logs message, intent, confidence, latency, feedback          │
 │ POST /api/feedback · GET /api/stats ─► /dashboard                                  │
 └────────────────────────────────────────────────────────────────────────────────────┘
```

**Ingredient matching:** for every recipe, FoodieBot computes *ingredients you have ÷ ingredients needed*. It ranks the best matches first (fewest missing ingredients, then quickest) and tells you exactly what's missing. Basics like salt and oil are treated as pantry items and don't count against a recipe.

## 📁 Project structure

```
CodeAlpha_Chatbot/
├── app.py                 # Flask web server + REST API
├── train.py               # trains the model, prints the accuracy report
├── chatbot/
│   ├── nlp.py             # text normalisation (lower-case, contractions, slang)
│   ├── model.py           # TF-IDF + Logistic Regression intent classifier
│   ├── recipes.py         # recipe search: ingredients, filters, ranking, substitutes
│   ├── bot.py             # conversation engine: context, diet memory, actions, fallback
│   └── store.py           # SQLite conversation log + analytics
├── data/
│   ├── intents.json       # training data: intents, patterns, responses
│   ├── recipes.json       # recipe knowledge base (31 recipes)
│   └── eval_set.json      # unseen phrasings for measuring accuracy
├── static/widget.js       # embeddable chat widget
├── templates/
│   ├── index.html         # FoodieBot website (ingredient picker + recipe cards)
│   └── dashboard.html     # analytics dashboard
├── tests/test_chatbot.py  # 30 automated tests
├── Dockerfile             # container image (trains the model at build time)
└── render.yaml            # one-click cloud deployment blueprint
```

---

## 🚀 Run locally

Requires Python 3.10+.

```bash
git clone https://github.com/<your-username>/CodeAlpha_Chatbot.git
cd CodeAlpha_Chatbot
pip install -r requirements.txt
python train.py        # trains the model and prints the accuracy report
python app.py          # http://localhost:5000
```

- FoodieBot website: <http://localhost:5000>
- Analytics dashboard: <http://localhost:5000/dashboard>

Run the tests:

```bash
python -m pytest -v
```

## 🐳 Run with Docker

```bash
docker build -t foodiebot .
docker run -p 8080:8080 foodiebot
```

Open <http://localhost:8080>.

## ☁️ Deploy to the cloud

The app is a container listening on `$PORT`, so it runs on any container platform:

- **Render (free)** — live at https://foodiebot-9i7c.onrender.com: in Render choose **New + → Web Service**, select the repo, set **Root Directory** to `CodeAlpha_Chatbot`, runtime **Docker**, plan **Free** and health check path `/health`.
- **Google Cloud Run**: `gcloud run deploy foodiebot --source . --allow-unauthenticated`
- **AWS App Runner / Azure Container Apps**: point them at the Docker image; health check path `/health`.

## 🔌 Add FoodieBot to any website

```html
<script src="https://foodiebot-9i7c.onrender.com/static/widget.js"
        data-title="FoodieBot" data-accent="#e8590c" defer></script>
```

JavaScript API: `FoodieChat.open()`, `FoodieChat.close()`, `FoodieChat.send("I have eggs and bread")`.

## 📡 API

```http
POST /api/chat
{"message": "I have eggs, onion and tomato", "session_id": "abc123"}
```
```json
{"reply": "🥕 With **egg, onion, tomato** you can make:\n\n1. 🍳 **Masala Omelette** — 3/5 ingredients ...",
 "intent": "ingredient_search", "confidence": 0.96,
 "suggestions": ["How to make Masala Omelette", "How to make Shakshuka", "How to make Roasted Tomato Soup"],
 "latency_ms": 1.4, "message_id": 1, "session_id": "abc123"}
```

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` | Send a message, get a reply |
| `POST /api/feedback` | `{"message_id": 1, "helpful": true}` |
| `GET /api/stats` | Analytics JSON |
| `GET /health` | Health check |

Configuration (environment variables): `PORT`, `DB_PATH`, `CONFIDENCE_THRESHOLD` (default 0.30), `RATE_LIMIT_PER_MIN` (default 30), `ALLOWED_ORIGIN` (default `*`).

## 🧠 Adding recipes and training

- **New recipe:** add an entry to `data/recipes.json` (name, aliases, cuisine, meals, diets, time, calories, ingredients, steps). No retraining needed.
- **New kind of question:** add an intent with example `patterns` to `data/intents.json`, then run `python train.py`. The app also retrains automatically on start if `intents.json` is newer than the saved model.
- Check `/dashboard` → *Unanswered questions* to see what users asked that FoodieBot didn't understand.

## 📊 Results

```
Intents: 15 | training patterns: 243 | recipes: 31
Held-out evaluation set (36 unseen phrasings): accuracy 100.0%
Response time: a few milliseconds per message
Tests: 30 passed
```

## 🛠️ Tech stack

Python · Flask · scikit-learn · SQLite · vanilla JavaScript · Docker · gunicorn

---

Made for the **CodeAlpha** Cloud Computing Internship.
