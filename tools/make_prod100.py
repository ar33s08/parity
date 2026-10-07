"""Generate the deterministic 100-prompt production corpus (seed 42)."""
import json
import random

rng = random.Random(42)
rows = []

for i in range(40):
    a, b = rng.randint(3, 97), rng.randint(2, 49)
    op = rng.choice(["*", "+", "-"])
    ans = {"*": a * b, "+": a + b, "-": a - b}[op]
    rows.append({"id": "math%03d" % i,
                 "prompt": "What is %d %s %d? Reply with just the number." % (a, op, b),
                 "must_contain": [str(ans)]})

conv = [(.5, "mile", "km", "0.8 km"), (3, "mile", "km", "4.8 km"), (10, "km", "mile", "6.2 mile"),
        (100, "C", "F", "212 F"), (37, "C", "F", "98.6 F"), (212, "F", "C", "100 C"),
        (5, "kg", "lb", "11.0 lb"), (20, "lb", "kg", "9.1 kg"), (3, "gallon", "liter", "11.4 liter"),
        (2, "liter", "gallon", "0.5 gallon"), (12, "inch", "cm", "30.5 cm"), (50, "cm", "inch", "19.7 inch"),
        (100, "km/h", "mph", "62.1 mph"), (60, "mph", "km/h", "96.6 km/h"), (7, "foot", "meter", "2.1 meter"),
        (30, "meter", "foot", "98.4 foot"), (4, "pint", "liter", "1.9 liter"), (1500, "gram", "lb", "3.3 lb"),
        (2.5, "mile", "km", "4.0 km"), (80, "km/h", "mph", "49.7 mph")]
for i, (v, f, t, a) in enumerate(conv):
    rows.append({"id": "conv%03d" % i,
                 "prompt": "Convert %s %s to %s. Reply only 'X %s' with X correct to 1 decimal." % (v, f, t, t),
                 "must_contain": [a]})

DQ = '"'
rows.append({"id": "json000",
             "prompt": "Return ONLY a JSON object with keys " + DQ + "name" + DQ + " (string) and " + DQ + "age" + DQ + " (int). No prose.",
             "regex": "\\{[\\s\\S]*\"name\"[\\s\\S]*\"age\""})
for i in range(19):
    keys = rng.sample(["id", "total", "count", "email", "status", "items", "price", "qty"], k=rng.randint(2, 3))
    rows.append({"id": "json%03d" % (i + 1),
                 "prompt": "Return ONLY a JSON object with %d keys: %s. Values any. No prose." % (
                     len(keys), ", ".join(DQ + k + DQ for k in keys)),
                 "regex": "[\\s\\S]*".join('\\"%s\\"' % k for k in keys)})

IF = [("List three primary colors. Do NOT mention green.", ["blue", "red"]),
      ("Name the three planets closest to the sun. Do not mention Earth.", ["Mercury", "Venus"]),
      ("Say exactly: hello world. Add nothing else.", ["hello world"]),
      ("Write a haiku about rain. It must contain the word 'rain'.", ["rain"]),
      ("Give one prime number between 20 and 30.", ["23"]),
      ("Spell 'necessary' correctly, in quotes only.", ["necessary"]),
      ("Give a JSON array with exactly 3 numbers, nothing else.", ["["]),
      ("Reply with the reverse of the word 'stressed'.", ["desserts"]),
      ("How many letters in 'banana'? Reply with just the number.", ["6"]),
      ("Convert binary 1010 to decimal, number only.", ["10"]),
      ("List two HTTP status codes for errors. Do not mention 200.", ["4"]),
      ("What does HTTP stand for? Include the substring 'rtp'.", ["rtp"]),
      ("Name HTTP methods: say 'GET' and one other.", ["GET"]),
      ("Write SQL: select all columns from users table. Start with SELECT.", ["SELECT"]),
      ("Git command to create a new branch named dev. One line.", ["branch"]),
      ("List the first three Fibonacci numbers, comma separated.", ["1"]),
      ("How many sides does a hexagon have? Number only.", ["6"]),
      ("Give the chemical symbol for gold, in quotes only.", ["Au"]),
      ("Say 'OK' and nothing else.", ["OK"]),
      ("One regex that matches a 5-digit zip code. No prose.", ["d{5}"])]
for i, (p, musts) in enumerate(IF):
    rows.append({"id": "instr%03d" % i, "prompt": p, "must_contain": musts})

with open("corpora/prod100.jsonl", "w") as f:
    for r in rows[:100]:
        f.write(json.dumps(r) + "\n")
print("wrote", min(100, len(rows)), "prompts")
