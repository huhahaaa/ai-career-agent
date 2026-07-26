import chromadb

client = chromadb.PersistentClient(path='./data/vector_store')
coll = client.get_collection('approved_jobs')
print(f'Collection name: {coll.name}')
print(f'Total count: {coll.count()}')

results = coll.get(include=['metadatas'])
types = {}
ids = []
for i, meta in enumerate(results['metadatas']):
    t = meta.get('type', 'job')
    types[t] = types.get(t, 0) + 1
    ids.append((results['ids'][i], t))

print(f'Type distribution: {types}')
print('First 15 IDs:')
for id, t in ids[:15]:
    print(f'  {id}: {t}')
