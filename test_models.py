import json, requests, time

cfg = json.load(open('config.json'))
key = cfg['api_key']

models_to_test = [
    'gemini-3.8-flash',
    'gemini-3.5-flash',
    'gemini-3.5-transcribe',
    'gemini-flash-latest'
]

results = {}
for m in models_to_test:
    t0 = time.time()
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        r = requests.post(url, json={'contents': [{'parts': [{'text': 'Hello'}]}]}, timeout=15)
        dt = time.time() - t0
        results[m] = {"status": r.status_code, "time": round(dt, 2), "resp": r.text[:150]}
    except Exception as e:
        results[m] = {"error": str(e)}

with open('test_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Done testing!")

