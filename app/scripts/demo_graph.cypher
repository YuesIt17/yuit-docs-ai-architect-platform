// Demo Neo4j inspection — only educational seed corpus (no PII).
// Run against live Neo4j after seed / sync_neo4j.

// Documents and classifications
MATCH (d:Document)
RETURN d.doc_id AS doc_id, d.corpus AS corpus, d.classification AS classification
ORDER BY d.corpus, d.doc_id
LIMIT 50;

// Product → allergen → policy (HAS_ALLERGEN / GOVERNS)
MATCH (prod:Document)-[:HAS_ALLERGEN]->(a:Entity {type:'allergen'})<-[:GOVERNS]-(pol:Document)
WHERE a.name IN ['gluten', 'nuts', 'milk']
RETURN prod.doc_id AS product, a.name AS allergen, pol.doc_id AS policy
LIMIT 50;

// Entity ABOUT links (legacy/general)
MATCH (e:Entity)-[:ABOUT]->(d:Document)
RETURN e.name, e.type, collect(d.doc_id) AS docs
LIMIT 50;
