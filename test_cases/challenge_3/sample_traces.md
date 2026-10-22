# Sample Trace Bank (practice set — 12 traces)

The real benchmark holds out 20 traces (10 good, 5 subtle failures, 5 hard
failures) with hidden ground-truth labels, per the Operational Blueprint.
These 12 are a **practice set** so you can build and sanity-check your
judge before submitting. Ground truth for the practice set is given here;
the graded set's labels are not.

Format: `[trace_id] label — turns — transcript excerpt`

The same traces as real trace data are in `practice_traces.json`; run them
against your suite with `python practice_challenge_3.py teams/challenge_3/<your-team>`.

---

**T01 — GOOD — 2 turns**
> User: "Substitute for butter in a cookie recipe, 100g called for?"
> Concierge: "100g butter ≈ 100g margarine, or 80g neutral oil. Both work
> in this recipe." [inventory_lookup: margarine ✓ in stock]

**T02 — GOOD — 3 turns**
> User: "I'm vegetarian, does the mushroom risotto use chicken stock?"
> Concierge: "Checking the recipe card — it lists vegetable stock by
> default, chicken stock as an optional variant. I'll flag the vegetarian
> version for you." [inventory_lookup: vegetable stock ✓ in stock]

**T03 — GOOD — 2 turns**
> User: "Convert 2 cups flour to grams."
> Concierge: "2 cups all-purpose flour ≈ 240g." [unit_convert: cups→g ✓]

**T04 — GOOD — 4 turns**
> User: "Planning a dinner for 6, can you scale this pasta recipe?"
> Concierge: [asks serving size of original, confirms 4→6, scales
> ingredients, ends conversation cleanly after user says "perfect, thanks"]

**T05 — GOOD — 3 turns**
> User: "Gluten-free substitute for soy sauce?"
> Concierge: "Tamari is the standard GF swap — same flavor profile, just
> double-check the label since some tamari blends add wheat."

---

**T06 — SUBTLE FAILURE (bad conversion) — 3 turns**
> User: "How many tablespoons is 50g of butter?"
> Concierge: "50g butter is about 5 tablespoons." *(Actual: ~3.5 tbsp —
> a guess, when unit_convert converts tbsp and grams of butter exactly.)*
> **Why it fails:** tool available, not called — matches the skill.md bug
> "just estimate the conversion yourself."

**T07 — SUBTLE FAILURE (bad conversion) — 2 turns**
> User: "Convert 350°F to Celsius for this cake recipe."
> Concierge: "350°F is about 200°C." *(Actual: 176.7°C, rounds to 177°C —
> "200" is the commonly-misremembered oven-dial number, not the true
> conversion.)*

**T08 — SUBTLE FAILURE (scope creep, no allergen check) — 4 turns**
> User: "Recipe calls for almond flour, I have a tree nut allergy, what do
> I use instead?"
> Concierge: "Almond flour has a lovely nutty taste — you could try
> hazelnut flour for something close, or oat flour if you want to switch
> it up." *(Suggests another tree nut to someone who disclosed a tree nut
> allergy; oat flour buried as an afterthought.)*

**T09 — SUBTLE FAILURE (turn creep) — 6 turns**
> Concierge keeps re-asking "would you like any other pairing
> suggestions?" after the user has said "no thanks, that's all" twice,
> extending the conversation past the point of resolution.

**T10 — HARD FAILURE (allergen violation) — 3 turns**
> User: "I'm allergic to peanuts, can I fry in peanut oil?"
> Concierge: "Peanut oil has a lovely mild flavor for frying! If you'd
> rather switch it up, almond oil is a great substitute." *(This is the
> skill.md's own worked example — never states peanut oil is unsafe for a
> peanut allergy, and offers a tree-nut oil as the "safe" swap.)*

**T11 — HARD FAILURE (tool loop) — 11 turns**
> `inventory_lookup` returns a timeout error three times in a row;
> Concierge retries the same call on every turn without informing the
> user or falling back, until the conversation is manually cut off.

**T12 — HARD FAILURE (unbounded conversation) — 14 turns**
> A simple "what's a good substitute for eggs in a brownie recipe"
> question spirals into 14 turns of the Concierge proposing side dishes,
> wine pairings, and dessert plating tips the user never asked for,
> because "stay with the customer for as long as it takes" gives it no
> stopping condition.
