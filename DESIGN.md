# Design Document: Shopkeeper Product Substitution Assistant

## Table of Contents
1. [System Overview](#system-overview)
2. [Knowledge Graph Modeling](#knowledge-graph-modeling)
3. [Search Approach](#search-approach)
4. [Constraint Handling](#constraint-handling)
5. [Rule-Based Explanation System](#rule-based-explanation-system)
6. [Implementation Details](#implementation-details)

---

## 1. System Overview

### 1.1 Problem Statement

When a customer requests a product that is out of stock, the shopkeeper needs to suggest alternative products that:
- Belong to the same or similar category
- Match customer's requirements (price, dietary restrictions, brand preferences)
- Are currently in stock

### 1.2 Solution Approach

We use a **Knowledge Graph** combined with **classical graph algorithms** (BFS) and **rule-based reasoning** to find and explain suitable alternatives.

**Key Design Decisions:**
- ✅ No Machine Learning or embeddings
- ✅ Pure graph traversal and logical reasoning
- ✅ Explainable recommendations through explicit rules
- ✅ Extensible and maintainable architecture

---

## 2. Knowledge Graph Modeling

### 2.1 Graph Schema

```
┌─────────────┐
│   Product   │ ──IS_A──→  ┌──────────┐
│             │            │ Category │
│  - name     │            │          │
│  - price    │ ←──IS_A─── │ - name   │
│  - stock    │            └──────────┘
│  - attrs    │                  │
└─────────────┘                  │ IS_A
      │                          ↓
      │ HAS_BRAND          ┌──────────┐
      |                    │ Category │
      |                    │ (Parent) │
┌─────────────┐            └──────────┘
│    Brand    │
│  - name     │
└─────────────┘

Product ←──SIMILAR_TO──→ Product
```

### 2.2 Node Types

#### 2.2.1 Product Nodes

**Attributes:**
```python
{
  "id": "prod_amul_taaza",
  "type": "product",
  "data": {
    "name": "Amul Taaza Milk 1L",
    "price": 54,
    "in_stock": False,
    "attributes": ["toned", "pasteurized"]
  }
}
```

**Design Rationale:**
- `in_stock`: Boolean flag for immediate availability check
- `attributes`: List of tags for filtering (vegetarian, lactose_free, etc.)
- `price`: Numeric value for price-based sorting and filtering

#### 2.2.2 Category Nodes

**Attributes:**
```python
{
  "id": "cat_milk",
  "type": "category",
  "data": {
    "name": "Milk"
  }
}
```

**Hierarchical Structure:**
```
Dairy Products (root)
├── Milk
├── Yogurt
└── Cheese

Snacks (root)
├── Biscuits
├── Chips
└── Namkeen
```

**Design Rationale:**
- Hierarchical categories allow finding alternatives at different specificity levels
- Example: If no "Toned Milk" available, suggest any "Milk", then any "Dairy"

#### 2.2.3 Brand Nodes

**Attributes:**
```python
{
  "id": "brand_amul",
  "type": "brand",
  "data": {
    "name": "Amul"
  }
}
```

**Design Rationale:**
- Separate brand nodes enable brand-based filtering
- Supports brand preference in scoring

### 2.3 Edge Types

#### 2.3.1 IS_A (Taxonomy)

**Direction:** Product → Category OR Category → Category

**Examples:**
```
prod_amul_taaza ─IS_A→ cat_milk
cat_milk ─IS_A→ cat_dairy
```

**Design Rationale:**
- Represents "type of" relationship
- Enables category-based search
- Supports hierarchical traversal

#### 2.3.2 HAS_BRAND (Attribution)

**Direction:** Product → Brand

**Example:**
```
prod_amul_taaza ─HAS_BRAND→ brand_amul
```

**Design Rationale:**
- Links products to manufacturers
- Enables brand preference matching
- Supports "same brand" alternatives

#### 2.3.3 SIMILAR_TO (Similarity)

**Direction:** Product ↔ Product (bidirectional)

**Example:**
```
prod_amul_gold ←─SIMILAR_TO(0.9)─→ prod_mother_dairy_full
```

**Attributes:**
- `weight`: Similarity score (0.0 to 1.0)

**Design Rationale:**
- Direct product-to-product similarity
- Higher weight = more similar
- Manually curated based on domain knowledge

### 2.4 Graph Statistics

| Metric | Count | Notes |
|--------|-------|-------|
| Total Nodes | 27 | 14 products + 7 categories + 6 brands |
| Product Nodes | 14 | Core inventory items |
| Category Nodes | 7 | Including hierarchies |
| Brand Nodes | 6 | Major brands |
| Total Edges | 42 | All relationships |
| IS_A Edges | 18 | Taxonomic relationships |
| HAS_BRAND Edges | 14 | Brand attributions |
| SIMILAR_TO Edges | 10 | Similarity links |

---

## 3. Search Approach

### 3.1 Algorithm Choice: Breadth-First Search (BFS)

**Why BFS?**

| Criterion | BFS | DFS | Dijkstra |
|-----------|-----|-----|----------|
| **Shortest Path** | ✅ Yes | ❌ No | ✅ Yes |
| **Level-by-level** | ✅ Yes | ❌ No | ❌ No |
| **Simplicity** | ✅ High | ✅ High | ❌ Medium |
| **Weighted Edges** | ❌ No | ❌ No | ✅ Yes |

**Decision:** BFS is chosen because:
1. Finds closest alternatives first (shortest path in unweighted graph)
2. Explores systematically by relationship distance
3. Simple to implement and understand
4. Edge weights are used in scoring, not traversal

### 3.2 Search Algorithm Details

#### 3.2.1 Pseudocode

```
FUNCTION find_alternatives(product_id, constraints):
    original_product = get_node(product_id)
    
    // Initialize BFS
    queue = Queue()
    queue.enqueue({id: product_id, distance: 0, path: []})
    visited = Set()
    candidates = []
    
    // BFS Traversal
    WHILE queue is not empty:
        current = queue.dequeue()
        
        IF current.id in visited:
            CONTINUE
        visited.add(current.id)
        
        node = get_node(current.id)
        
        // Evaluate product nodes
        IF node.type == 'product' AND node != original_product:
            score = score_product(node, original_product, constraints, current.distance)
            IF score > 0:
                candidates.append({
                    product: node,
                    score: score,
                    distance: current.distance,
                    path: current.path
                })
        
        // Explore outgoing edges
        FOR EACH edge in get_outgoing_edges(current.id):
            IF edge.to NOT in visited:
                queue.enqueue({
                    id: edge.to,
                    distance: current.distance + 1,
                    path: current.path + [edge.relation]
                })
        
        // Explore incoming edges (for reverse traversal)
        FOR EACH edge in get_incoming_edges(current.id):
            IF edge.from NOT in visited:
                queue.enqueue({
                    id: edge.from,
                    distance: current.distance + 1,
                    path: current.path + ['reverse_' + edge.relation]
                })
    
    // Sort and return top 3
    candidates.sort(by score, descending)
    RETURN candidates[0:3]
```

#### 3.2.2 Traversal Example

**Scenario:** Find alternatives for "Amul Taaza Milk" (out of stock)

```
Step 1: Start Node
┌─────────────────┐
│ prod_amul_taaza │  Distance: 0
└─────────────────┘

Step 2: First Level (Distance 1)
prod_amul_taaza ──IS_A──→ cat_milk
prod_amul_taaza ──HAS_BRAND──→ brand_amul

Step 3: Second Level (Distance 2)
cat_milk ←──IS_A── prod_mother_dairy_toned  [CANDIDATE]
cat_milk ←──IS_A── prod_nestle_slim          [CANDIDATE]
cat_milk ──IS_A──→ cat_dairy

Step 4: Third Level (Distance 3)
cat_dairy ←──IS_A── prod_amul_yogurt         [CANDIDATE - different category]

Step 5: Score and Rank
1. Mother Dairy Toned: Score 87 (same category, cheaper)
2. Nestle Slim: Score 75 (same category, special attributes)
3. Amul Yogurt: Score 45 (related category, different product type)
```

### 3.3 Time Complexity Analysis

- **Graph Size:** V = 27 nodes, E = 42 edges
- **BFS Complexity:** O(V + E) = O(69) ≈ O(1) for this scale
- **Scoring:** O(C) per candidate, C = number of candidates found
- **Total:** O(V + E + C) ≈ O(V + E) = **O(n)** linear time

**Scalability:** For 1000 products, still ~O(1000) operations, acceptable for real-time use.

---

## 4. Constraint Handling

### 4.1 Constraint Types

#### 4.1.1 Hard Constraints (Filters)

Products **must** satisfy these or score = 0:

| Constraint | Type | Check | Example |
|------------|------|-------|---------|
| **Stock Availability** | Boolean | `in_stock == True` | Must be available |
| **Price Limit** | Numeric | `price <= max_price` | Price ≤ ₹60 |
| **Required Attributes** | Set | `required ⊆ attributes` | Must have "vegetarian" |

#### 4.1.2 Soft Constraints (Scoring Factors)

Influence score but don't eliminate:

| Factor | Impact | Range |
|--------|--------|-------|
| **Category Match** | +50 | Same category bonus |
| **Brand Preference** | +0 to +30 | Preferred/same brand |
| **Price Similarity** | +0 to +20 | Closer price |
| **Attribute Overlap** | +0 to +50 | More overlap = higher |
| **Graph Distance** | -10 per hop | Penalty for distance |

### 4.2 Constraint Implementation

#### 4.2.1 Hard Constraint Filtering

```python
def score_product(candidate, original, constraints, distance):
    score = 100
    
    # HARD CONSTRAINT 1: Stock
    if not candidate.data['in_stock']:
        return 0  # Eliminate immediately
    
    # HARD CONSTRAINT 2: Price
    if constraints.get('maxPrice'):
        if candidate.data['price'] > constraints['maxPrice']:
            return 0
    
    # HARD CONSTRAINT 3: Required Attributes
    required_tags = constraints.get('requiredTags', [])
    candidate_tags = set(candidate.data.get('attributes', []))
    for tag in required_tags:
        if tag not in candidate_tags:
            return 0  # Missing required attribute
    
    # Continue with scoring...
```

#### 4.2.2 Soft Constraint Scoring

```python
    # SOFT CONSTRAINT 1: Category Match
    if same_category(candidate, original):
        score += 50
    
    # SOFT CONSTRAINT 2: Brand
    if preferred_brand and candidate_brand == preferred_brand:
        score += 30
    elif candidate_brand == original_brand:
        score += 20
    
    # SOFT CONSTRAINT 3: Price Similarity
    price_diff = abs(candidate.price - original.price)
    score += max(0, 20 - price_diff)
    
    # SOFT CONSTRAINT 4: Attribute Overlap
    overlap = len(candidate_attrs & original_attrs)
    score += overlap * 5
    
    # SOFT CONSTRAINT 5: Distance Penalty
    score -= distance * 10
    
    return score
```

### 4.3 Score Distribution Example

**Original Product:** Amul Taaza Milk (₹54, toned, pasteurized)

**Candidate 1:** Mother Dairy Toned (₹52)
```
Base:           100
Distance (-2):   80
Category (+50): 130
Price (+18):    148
Attrs (+10):    158
Final Score:    158 ✅ BEST
```

**Candidate 2:** Nestle Slim (₹58)
```
Base:           100
Distance (-2):   80
Category (+50): 130
Price (+16):    146
Attrs (+5):     151
Final Score:    151
```

**Candidate 3:** Amul Yogurt (₹45) - Different category
```
Base:           100
Distance (-3):   70
Category (+0):   70  [NOT same category]
Price (+11):     81
Attrs (+0):      81
Final Score:     81
```

---

## 5. Rule-Based Explanation System

### 5.1 Explanation Architecture

```
┌─────────────────────────────────────────┐
│      Recommendation Generated           │
│  (Candidate Product + Score)            │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         Rule Engine                     │
│  ┌────────────────────────────────┐    │
│  │ Rule 1: Category Analysis      │    │
│  ├────────────────────────────────┤    │
│  │ Rule 2: Brand Analysis         │    │
│  ├────────────────────────────────┤    │
│  │ Rule 3: Price Comparison       │    │
│  ├────────────────────────────────┤    │
│  │ Rule 4: Attribute Matching     │    │
│  └────────────────────────────────┘    │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│    Human-Readable Explanations          │
│  • [same_category_match] Same category  │
│  • [cheaper_option] Cheaper by ₹2       │
│  • [all_required_tags_matched]          │
└─────────────────────────────────────────┘
```

### 5.2 Rule Definitions

#### Rule 1: Category Match Rule

```python
IF candidate.category == original.category:
    APPLY "same_category_match"
    TEXT = "Same category: {category_name}"
ELSE:
    APPLY "related_category"
    TEXT = "Related category: {category_name}"
```

**Example Output:**
- `[same_category_match] Same category: Milk`
- `[related_category] Related category: Dairy Products`

#### Rule 2: Brand Match Rule

```python
IF candidate.brand == user_preferred_brand:
    APPLY "preferred_brand"
    TEXT = "Preferred brand: {brand_name}"
ELSE IF candidate.brand == original.brand:
    APPLY "same_brand"
    TEXT = "Same brand: {brand_name}"
ELSE:
    APPLY "different_brand"
    TEXT = "Alternative brand: {brand_name}"
```

**Example Output:**
- `[preferred_brand] Preferred brand: Mother Dairy`
- `[same_brand] Same brand: Amul`

#### Rule 3: Price Comparison Rule

```python
price_diff = candidate.price - original.price

IF price_diff < 0:
    APPLY "cheaper_option"
    TEXT = "Cheaper: ₹{candidate_price} vs ₹{original_price}"
ELSE IF price_diff == 0:
    APPLY "same_price"
    TEXT = "Same price: ₹{price}"
ELSE IF price_diff <= 10:
    APPLY "slightly_expensive"
    TEXT = "Slightly more: ₹{candidate_price} (+ ₹{diff})"
ELSE:
    APPLY "more_expensive"
    TEXT = "Higher price: ₹{candidate_price} (+ ₹{diff})"
```

**Example Output:**
- `[cheaper_option] Cheaper: ₹52 vs ₹54`
- `[same_price] Same price: ₹20`

#### Rule 4: Attribute Matching Rule

```python
required_tags = user_constraints.required_tags

IF required_tags AND ALL(tag in candidate.attributes for tag in required_tags):
    APPLY "all_required_tags_matched"
    TEXT = "Matches all filters: {', '.join(required_tags)}"

extra_attrs = candidate.attributes - required_tags
IF extra_attrs:
    APPLY "additional_attributes"
    TEXT = "Also has: {', '.join(extra_attrs[:3])}"
```

**Example Output:**
- `[all_required_tags_matched] Matches all filters: vegetarian, low_sugar`
- `[additional_attributes] Also has: pasteurized, probiotic, no_sugar`

### 5.3 Complete Explanation Example

**Scenario:** User searches for Parle-G (out of stock)
- Max Price: ₹25
- Required: vegetarian, low_sugar
- Preferred Brand: Britannia

**Top Alternative:** Britannia Marie Gold (₹25)

**Generated Explanations:**
```
📋 Why this alternative?

• [same_category_match] Same category: Biscuits
  ↳ Belongs to the exact same product category as requested

• [preferred_brand] Preferred brand: Britannia
  ↳ Matches your brand preference

• [same_price] Same price: ₹25
  ↳ No price difference from original product

• [all_required_tags_matched] Matches all filters: vegetarian, low_sugar
  ↳ Satisfies all your dietary requirements

• [additional_attributes] Also has: whole_wheat
  ↳ Extra beneficial features not in original
```

---

## 6. Implementation Details

### 6.1 Data Structures

#### 6.1.1 Graph Representation

**Choice:** Adjacency List (List of Edges)

```python
class KnowledgeGraph:
    nodes: Dict[str, Node] = {}
    edges: List[Edge] = []
```

**Why not Adjacency Matrix?**
- Sparse graph (42 edges for 27 nodes)
- Matrix would be 27×27 = 729 cells (wasteful)
- List representation: O(E) space vs O(V²) space

#### 6.1.2 Node Storage

```python
class Node:
    id: str           # Unique identifier
    type: str         # 'product', 'category', or 'brand'
    data: Dict        # Flexible attributes
```

**Design Rationale:**
- `Dict` storage allows flexible attributes per node type
- No need for separate classes for each node type

#### 6.1.3 Edge Storage

```python
class Edge:
    from_node: str    # Source node ID
    to_node: str      # Target node ID
    relation: str     # 'IS_A', 'HAS_BRAND', 'SIMILAR_TO'
    weight: float     # Optional weight (default 1.0)
```

### 6.2 Performance Optimizations

#### 6.2.1 Visited Set

```python
visited = set()  # O(1) lookup
```

**Why:** Prevents revisiting nodes, crucial for graphs with cycles

#### 6.2.2 Early Termination

```python
if len(candidates) >= 10:  # Collect more than needed
    break
```

**Why:** Stop searching once enough candidates found

#### 6.2.3 Score Caching

```python
# Cache frequently accessed graph queries
@functools.lru_cache(maxsize=128)
def get_category(product_id):
    return find_category_edge(product_id)
```

### 6.3 Error Handling

#### 6.3.1 Missing Node Handling

```python
def get_node(self, id: str) -> Optional[Node]:
    return self.nodes.get(id)  # Returns None if not found
```

#### 6.3.2 Empty Results

```python
if not alternatives:
    return {
        'error': 'No alternatives found',
        'suggestion': 'Try relaxing constraints'
    }
```

#### 6.3.3 Invalid Constraints

```python
if max_price and max_price < 0:
    raise ValueError("Max price cannot be negative")
```

### 6.4 Extensibility

#### 6.4.1 Adding New Node Types

```python
# Easy to add new node types
kg.add_node('attr_organic', 'attribute', {
    'name': 'Organic',
    'category': 'certification'
})
```

#### 6.4.2 Adding New Edge Types

```python
# Support new relationships
kg.add_edge('prod_x', 'prod_y', 'FREQUENTLY_BOUGHT_TOGETHER', 0.85)
```

#### 6.4.3 Custom Scoring Functions

```python
def score_product_custom(candidate, original, constraints, distance):
    score = base_score_product(...)
    
    # Add custom business logic
    if candidate.data.get('on_sale'):
        score += 25
    
    if candidate.data.get('expiry_soon'):
        score -= 30
    
    return score
```

---

## 7. Sample Rule Tags and Human Explanations

### 7.1 Complete Rule Reference Table

| Rule Tag | Trigger Condition | Human Explanation Template |
|----------|-------------------|----------------------------|
| `same_category_match` | Candidate in exact same category | "Same category: {category}" |
| `related_category` | Candidate in related/parent category | "Related category: {category}" |
| `same_brand` | Same brand as original | "Same brand: {brand}" |
| `preferred_brand` | Matches user's brand preference | "Preferred brand: {brand}" |
| `different_brand` | Different brand | "Alternative brand: {brand}" |
| `cheaper_option` | Price < original price | "Cheaper: ₹{price} vs ₹{original}" |
| `same_price` | Price == original price | "Same price: ₹{price}" |
| `slightly_expensive` | Price 1-10₹ more | "Slightly more: +₹{diff}" |
| `all_required_tags_matched` | Has all required attributes | "Matches all filters: {tags}" |
| `additional_attributes` | Has extra beneficial attributes | "Also has: {extra_attrs}" |
| `high_similarity` | SIMILAR_TO edge with weight > 0.8 | "Very similar product" |
| `in_stock_advantage` | Original out of stock, this available | "Currently available" |
| `distance_close` | Graph distance ≤ 2 | "Closely related product" |

### 7.2 Example Rule Combinations

#### Scenario A: Perfect Match (Different Brand)
```
Product: Amul Gold Milk → Mother Dairy Full Cream

Rules Applied:
1. [same_category_match] Same category: Milk
2. [different_brand] Alternative brand: Mother Dairy
3. [cheaper_option] Cheaper: ₹64 vs ₹66
4. [all_required_tags_matched] Matches: full_cream, pasteurized

Explanation Quality: ⭐⭐⭐⭐⭐
Reason: Clear, specific, actionable
```

#### Scenario B: Related Category Match
```
Product: Amul Taaza Milk → Amul Yogurt

Rules Applied:
1. [related_category] Related category: Dairy Products
2. [same_brand] Same brand: Amul
3. [cheaper_option] Cheaper: ₹45 vs ₹54
4. [additional_attributes] Also has: probiotic, no_sugar

Explanation Quality: ⭐⭐⭐⭐
Reason: Honest about category difference, highlights benefits
```

#### Scenario C: Exact Substitute
```
Product: Lays Classic → Lays Cream & Onion

Rules Applied:
1. [same_category_match] Same category: Chips
2. [same_brand] Same brand: Lays
3. [same_price] Same price: ₹20
4. [high_similarity] Very similar product
5. [all_required_tags_matched] Matches: vegetarian

Explanation Quality: ⭐⭐⭐⭐⭐
Reason: Nearly identical product, perfect substitute
```

---

## 8. Future Enhancements

### 8.1 Potential Improvements

1. **Dynamic Pricing**
   - Add time-based price adjustments
   - Seasonal discounts

2. **User Feedback Loop**
   - Track which alternatives users accept
   - Adjust scoring weights based on acceptance rate

3. **Inventory Management Integration**
   - Real-time stock updates
   - Reorder suggestions

4. **Multi-Language Support**
   - Localized product names
   - Regional attribute tags

5. **Advanced Similarity**
   - Compute SIMILAR_TO edges automatically
   - Use product descriptions for similarity

### 8.2 Scalability Considerations

**For 10,000+ products:**
- Index nodes by type for faster filtering
- Use database instead of in-memory storage
- Implement pagination for results
- Add caching layer (Redis)

---

## 9. Conclusion

This design document provides a comprehensive overview of the Knowledge Graph-based product substitution system. The system combines classical graph algorithms (BFS) with rule-based reasoning to provide explainable, relevant product recommendations without relying on machine learning.

**Key Strengths:**
- ✅ Fully explainable recommendations
- ✅ Fast performance (linear time complexity)
- ✅ Flexible constraint handling
- ✅ Easy to extend and maintain
- ✅ No black-box ML models

**Core Philosophy:** "Transparency over complexity" - every recommendation can be traced back to explicit rules and graph relationships.
