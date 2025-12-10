"""
Shopkeeper Product Substitution Assistant
A Knowledge Graph-based product recommendation system using graph search and rule-based reasoning
"""

import streamlit as st
import json
from collections import deque
from typing import List, Dict, Tuple, Optional

# =====================================================
# KNOWLEDGE GRAPH IMPLEMENTATION
# =====================================================

class Node:
    """Represents a node in the Knowledge Graph"""
    def __init__(self, id: str, node_type: str, data: Dict):
        self.id = id
        self.type = node_type
        self.data = data

class Edge:
    """Represents an edge/relationship in the Knowledge Graph"""
    def __init__(self, from_node: str, to_node: str, relation: str, weight: float = 1.0):
        self.from_node = from_node
        self.to_node = to_node
        self.relation = relation
        self.weight = weight

class KnowledgeGraph:
    """
    Knowledge Graph implementation for product substitution
    Uses graph traversal (BFS) and rule-based scoring
    """
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
    
    def add_node(self, id: str, node_type: str, data: Dict):
        """Add a node to the graph"""
        self.nodes[id] = Node(id, node_type, data)
    
    def add_edge(self, from_node: str, to_node: str, relation: str, weight: float = 1.0):
        """Add an edge/relationship to the graph"""
        self.edges.append(Edge(from_node, to_node, relation, weight))
    
    def get_node(self, id: str) -> Optional[Node]:
        """Retrieve a node by ID"""
        return self.nodes.get(id)
    
    def get_outgoing_edges(self, node_id: str, relation: Optional[str] = None) -> List[Edge]:
        """Get all outgoing edges from a node (optionally filtered by relation type)"""
        return [e for e in self.edges 
                if e.from_node == node_id and (relation is None or e.relation == relation)]
    
    def get_incoming_edges(self, node_id: str, relation: Optional[str] = None) -> List[Edge]:
        """Get all incoming edges to a node (optionally filtered by relation type)"""
        return [e for e in self.edges 
                if e.to_node == node_id and (relation is None or e.relation == relation)]
    
    def find_alternatives(self, product_id: str, constraints: Dict) -> List[Dict]:
        """
        Find alternative products using BFS graph traversal
        
        Algorithm:
        1. Start from requested product node
        2. Use BFS to explore connected nodes (categories, brands, similar products)
        3. Score each product candidate based on multiple factors
        4. Return top 3 alternatives
        
        Args:
            product_id: ID of the out-of-stock product
            constraints: Dictionary with maxPrice, requiredTags, preferredBrand
            
        Returns:
            List of candidate products with scores and explanations
        """
        original_product = self.get_node(product_id)
        if not original_product:
            return []
        
        # BFS initialization
        visited = set()
        queue = deque([{
            'id': product_id,
            'distance': 0,
            'path': []
        }])
        
        candidates = []
        
        # BFS traversal
        while queue:
            current = queue.popleft()
            
            if current['id'] in visited:
                continue
            visited.add(current['id'])
            
            node = self.get_node(current['id'])
            
            # If it's a product node (and not the original), evaluate it
            if node and node.type == 'product' and current['id'] != product_id:
                score = self._score_product(node, original_product, constraints, current['distance'])
                if score > 0:
                    candidates.append({
                        'product': node,
                        'score': score,
                        'distance': current['distance'],
                        'path': current['path']
                    })
            
            # Explore neighbors - outgoing edges
            for edge in self.get_outgoing_edges(current['id']):
                if edge.to_node not in visited:
                    queue.append({
                        'id': edge.to_node,
                        'distance': current['distance'] + 1,
                        'path': current['path'] + [edge.relation]
                    })
            
            # Explore neighbors - incoming edges (for category traversal)
            for edge in self.get_incoming_edges(current['id']):
                if edge.from_node not in visited:
                    queue.append({
                        'id': edge.from_node,
                        'distance': current['distance'] + 1,
                        'path': current['path'] + [f'reverse_{edge.relation}']
                    })
        
        # Sort by score and return top 3
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:3]
    
    def _score_product(self, candidate: Node, original: Node, constraints: Dict, distance: int) -> float:
        """
        Score a candidate product based on multiple factors
        
        Scoring Rules:
        - Base score: 100
        - Distance penalty: -10 per graph hop
        - Same category: +50
        - Brand match: +20-30
        - Price similarity: +0 to +20
        - Attribute overlap: +5 per matching attribute
        
        Hard Constraints:
        - Must be in stock (return 0 if not)
        - Must meet price limit (return 0 if over)
        - Must have all required tags (return 0 if missing any)
        """
        score = 100.0
        candidate_data = candidate.data
        
        # HARD CONSTRAINT 1: Must be in stock
        if not candidate_data.get('in_stock', False):
            return 0
        
        # HARD CONSTRAINT 2: Price limit
        if constraints.get('maxPrice') and candidate_data['price'] > constraints['maxPrice']:
            return 0
        
        # HARD CONSTRAINT 3: Required tags
        required_tags = constraints.get('requiredTags', [])
        if required_tags:
            candidate_tags = set(candidate_data.get('attributes', []))
            for tag in required_tags:
                if tag not in candidate_tags:
                    return 0
        
        # SCORING FACTOR 1: Distance penalty (graph traversal distance)
        score -= distance * 10
        
        # SCORING FACTOR 2: Category match
        candidate_category = self._get_category(candidate.id)
        original_category = self._get_category(original.id)
        if candidate_category == original_category:
            score += 50  # Same category bonus
        
        # SCORING FACTOR 3: Brand preference
        candidate_brand = self._get_brand(candidate.id)
        original_brand = self._get_brand(original.id)
        preferred_brand = constraints.get('preferredBrand')
        
        if preferred_brand and candidate_brand == preferred_brand:
            score += 30  # Preferred brand bonus
        elif candidate_brand == original_brand:
            score += 20  # Same brand bonus
        
        # SCORING FACTOR 4: Price similarity
        price_diff = abs(candidate_data['price'] - original.data['price'])
        price_score = max(0, 20 - price_diff)
        score += price_score
        
        # SCORING FACTOR 5: Attribute overlap
        original_attrs = set(original.data.get('attributes', []))
        candidate_attrs = set(candidate_data.get('attributes', []))
        overlap_count = len(original_attrs & candidate_attrs)
        score += overlap_count * 5
        
        return score
    
    def _get_category(self, product_id: str) -> Optional[str]:
        """Get the category of a product via IS_A edge"""
        edges = self.get_outgoing_edges(product_id, 'IS_A')
        return edges[0].to_node if edges else None
    
    def _get_brand(self, product_id: str) -> Optional[str]:
        """Get the brand of a product via HAS_BRAND edge"""
        edges = self.get_outgoing_edges(product_id, 'HAS_BRAND')
        return edges[0].to_node if edges else None
    
    def generate_explanation(self, candidate: Dict, original: Node, constraints: Dict) -> List[Dict]:
        """
        Generate rule-based explanations for why this product was recommended
        
        Rules Applied:
        - same_category_match: Product in same category
        - related_category: Product in related category
        - same_brand: Same brand as original
        - preferred_brand: Matches user's preferred brand
        - cheaper_option: Lower price than original
        - same_price: Same price as original
        - all_required_tags_matched: Meets all user filters
        - additional_attributes: Has extra beneficial attributes
        """
        rules = []
        candidate_product = candidate['product']
        candidate_data = candidate_product.data
        
        # Get category and brand info
        candidate_category = self._get_category(candidate_product.id)
        original_category = self._get_category(original.id)
        candidate_brand = self._get_brand(candidate_product.id)
        original_brand = self._get_brand(original.id)
        
        category_node = self.get_node(candidate_category) if candidate_category else None
        brand_node = self.get_node(candidate_brand) if candidate_brand else None
        
        # RULE 1: Category Match
        if candidate_category == original_category:
            rules.append({
                'rule': 'same_category_match',
                'text': f"Same category: {category_node.data['name'] if category_node else 'Unknown'}"
            })
        else:
            rules.append({
                'rule': 'related_category',
                'text': f"Related category: {category_node.data['name'] if category_node else 'Unknown'}"
            })
        
        # RULE 2: Brand Match
        if candidate_brand == original_brand:
            rules.append({
                'rule': 'same_brand',
                'text': f"Same brand: {brand_node.data['name'] if brand_node else 'Unknown'}"
            })
        elif constraints.get('preferredBrand') and candidate_brand == constraints['preferredBrand']:
            rules.append({
                'rule': 'preferred_brand',
                'text': f"Preferred brand: {brand_node.data['name'] if brand_node else 'Unknown'}"
            })
        
        # RULE 3: Price Comparison
        if candidate_data['price'] < original.data['price']:
            rules.append({
                'rule': 'cheaper_option',
                'text': f"Cheaper: ₹{candidate_data['price']} vs ₹{original.data['price']}"
            })
        elif candidate_data['price'] == original.data['price']:
            rules.append({
                'rule': 'same_price',
                'text': f"Same price: ₹{candidate_data['price']}"
            })
        
        # RULE 4: Required Tags Matched
        required_tags = constraints.get('requiredTags', [])
        if required_tags:
            rules.append({
                'rule': 'all_required_tags_matched',
                'text': f"Matches all filters: {', '.join(required_tags)}"
            })
        
        # RULE 5: Additional Attributes
        candidate_attrs = candidate_data.get('attributes', [])
        extra_attrs = [a for a in candidate_attrs if a not in required_tags]
        if extra_attrs:
            rules.append({
                'rule': 'additional_attributes',
                'text': f"Also has: {', '.join(extra_attrs[:3])}"  # Show max 3
            })
        
        return rules
    
    def load_from_json(self, filepath: str):
        """Load Knowledge Graph from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Load nodes
        for node in data['nodes']:
            self.add_node(node['id'], node['type'], node['data'])
        
        # Load edges
        for edge in data['edges']:
            self.add_edge(
                edge['from'],
                edge['to'],
                edge['relation'],
                edge.get('weight', 1.0)
            )


# =====================================================
# DATA INITIALIZATION
# =====================================================

def initialize_knowledge_graph() -> KnowledgeGraph:
    """Initialize the Knowledge Graph with product data"""
    kg = KnowledgeGraph()
    
    # ===== CATEGORIES =====
    kg.add_node('cat_dairy', 'category', {'name': 'Dairy Products'})
    kg.add_node('cat_milk', 'category', {'name': 'Milk'})
    kg.add_node('cat_yogurt', 'category', {'name': 'Yogurt'})
    kg.add_node('cat_beverages', 'category', {'name': 'Beverages'})
    kg.add_node('cat_snacks', 'category', {'name': 'Snacks'})
    kg.add_node('cat_biscuits', 'category', {'name': 'Biscuits'})
    kg.add_node('cat_chips', 'category', {'name': 'Chips'})
    kg.add_node('cat_bread', 'category', {'name': 'Bread & Bakery'})
    
    # ===== BRANDS =====
    kg.add_node('brand_amul', 'brand', {'name': 'Amul'})
    kg.add_node('brand_mother_dairy', 'brand', {'name': 'Mother Dairy'})
    kg.add_node('brand_nestle', 'brand', {'name': 'Nestle'})
    kg.add_node('brand_britannia', 'brand', {'name': 'Britannia'})
    kg.add_node('brand_parle', 'brand', {'name': 'Parle'})
    kg.add_node('brand_lays', 'brand', {'name': 'Lays'})
    kg.add_node('brand_kurkure', 'brand', {'name': 'Kurkure'})
    
    # ===== PRODUCTS - DAIRY =====
    kg.add_node('prod_amul_gold', 'product', {
        'name': 'Amul Gold Milk 1L',
        'price': 66,
        'in_stock': True,
        'attributes': ['full_cream', 'pasteurized']
    })
    
    kg.add_node('prod_amul_taaza', 'product', {
        'name': 'Amul Taaza Milk 1L',
        'price': 54,
        'in_stock': False,  # OUT OF STOCK
        'attributes': ['toned', 'pasteurized']
    })
    
    kg.add_node('prod_mother_dairy_full', 'product', {
        'name': 'Mother Dairy Full Cream 1L',
        'price': 64,
        'in_stock': True,
        'attributes': ['full_cream', 'pasteurized']
    })
    
    kg.add_node('prod_nestle_slim', 'product', {
        'name': 'Nestle Slim Milk 1L',
        'price': 58,
        'in_stock': True,
        'attributes': ['low_fat', 'lactose_free', 'pasteurized']
    })
    
    kg.add_node('prod_mother_dairy_toned', 'product', {
        'name': 'Mother Dairy Toned Milk 1L',
        'price': 52,
        'in_stock': True,
        'attributes': ['toned', 'pasteurized']
    })
    
    kg.add_node('prod_amul_yogurt', 'product', {
        'name': 'Amul Yogurt 400g',
        'price': 45,
        'in_stock': True,
        'attributes': ['probiotic', 'no_sugar']
    })
    
    # ===== PRODUCTS - BISCUITS =====
    kg.add_node('prod_parle_g', 'product', {
        'name': 'Parle-G Biscuits 200g',
        'price': 20,
        'in_stock': False,  # OUT OF STOCK
        'attributes': ['vegetarian', 'glucose']
    })
    
    kg.add_node('prod_britannia_marie', 'product', {
        'name': 'Britannia Marie Gold 200g',
        'price': 25,
        'in_stock': True,
        'attributes': ['vegetarian', 'low_sugar']
    })
    
    kg.add_node('prod_parle_monaco', 'product', {
        'name': 'Parle Monaco 200g',
        'price': 22,
        'in_stock': True,
        'attributes': ['vegetarian', 'salty']
    })
    
    kg.add_node('prod_britannia_good_day', 'product', {
        'name': 'Britannia Good Day 200g',
        'price': 30,
        'in_stock': True,
        'attributes': ['vegetarian', 'butter_cookies']
    })
    
    kg.add_node('prod_parle_krackjack', 'product', {
        'name': 'Parle Krackjack 200g',
        'price': 20,
        'in_stock': True,
        'attributes': ['vegetarian', 'salty']
    })
    
    # ===== PRODUCTS - CHIPS =====
    kg.add_node('prod_lays_classic', 'product', {
        'name': 'Lays Classic Salted 100g',
        'price': 20,
        'in_stock': False,  # OUT OF STOCK
        'attributes': ['vegetarian', 'salty']
    })
    
    kg.add_node('prod_lays_cream_onion', 'product', {
        'name': 'Lays Cream & Onion 100g',
        'price': 20,
        'in_stock': True,
        'attributes': ['vegetarian']
    })
    
    kg.add_node('prod_kurkure_masala', 'product', {
        'name': 'Kurkure Masala Munch 100g',
        'price': 20,
        'in_stock': True,
        'attributes': ['vegetarian', 'spicy']
    })
    
    # ===== PRODUCT TO CATEGORY EDGES =====
    # Milk products
    kg.add_edge('prod_amul_gold', 'cat_milk', 'IS_A')
    kg.add_edge('prod_amul_taaza', 'cat_milk', 'IS_A')
    kg.add_edge('prod_mother_dairy_full', 'cat_milk', 'IS_A')
    kg.add_edge('prod_nestle_slim', 'cat_milk', 'IS_A')
    kg.add_edge('prod_mother_dairy_toned', 'cat_milk', 'IS_A')
    kg.add_edge('cat_milk', 'cat_dairy', 'IS_A')
    
    # Yogurt products
    kg.add_edge('prod_amul_yogurt', 'cat_yogurt', 'IS_A')
    kg.add_edge('cat_yogurt', 'cat_dairy', 'IS_A')
    
    # Biscuit products
    kg.add_edge('prod_parle_g', 'cat_biscuits', 'IS_A')
    kg.add_edge('prod_britannia_marie', 'cat_biscuits', 'IS_A')
    kg.add_edge('prod_parle_monaco', 'cat_biscuits', 'IS_A')
    kg.add_edge('prod_britannia_good_day', 'cat_biscuits', 'IS_A')
    kg.add_edge('prod_parle_krackjack', 'cat_biscuits', 'IS_A')
    kg.add_edge('cat_biscuits', 'cat_snacks', 'IS_A')
    
    # Chips products
    kg.add_edge('prod_lays_classic', 'cat_chips', 'IS_A')
    kg.add_edge('prod_lays_cream_onion', 'cat_chips', 'IS_A')
    kg.add_edge('prod_kurkure_masala', 'cat_chips', 'IS_A')
    kg.add_edge('cat_chips', 'cat_snacks', 'IS_A')
    
    # ===== PRODUCT TO BRAND EDGES =====
    kg.add_edge('prod_amul_gold', 'brand_amul', 'HAS_BRAND')
    kg.add_edge('prod_amul_taaza', 'brand_amul', 'HAS_BRAND')
    kg.add_edge('prod_amul_yogurt', 'brand_amul', 'HAS_BRAND')
    kg.add_edge('prod_mother_dairy_full', 'brand_mother_dairy', 'HAS_BRAND')
    kg.add_edge('prod_mother_dairy_toned', 'brand_mother_dairy', 'HAS_BRAND')
    kg.add_edge('prod_nestle_slim', 'brand_nestle', 'HAS_BRAND')
    kg.add_edge('prod_parle_g', 'brand_parle', 'HAS_BRAND')
    kg.add_edge('prod_parle_monaco', 'brand_parle', 'HAS_BRAND')
    kg.add_edge('prod_parle_krackjack', 'brand_parle', 'HAS_BRAND')
    kg.add_edge('prod_britannia_marie', 'brand_britannia', 'HAS_BRAND')
    kg.add_edge('prod_britannia_good_day', 'brand_britannia', 'HAS_BRAND')
    kg.add_edge('prod_lays_classic', 'brand_lays', 'HAS_BRAND')
    kg.add_edge('prod_lays_cream_onion', 'brand_lays', 'HAS_BRAND')
    kg.add_edge('prod_kurkure_masala', 'brand_kurkure', 'HAS_BRAND')
    
    # ===== SIMILARITY EDGES =====
    kg.add_edge('prod_amul_gold', 'prod_mother_dairy_full', 'SIMILAR_TO', 0.9)
    kg.add_edge('prod_mother_dairy_full', 'prod_amul_gold', 'SIMILAR_TO', 0.9)
    kg.add_edge('prod_parle_g', 'prod_britannia_marie', 'SIMILAR_TO', 0.8)
    kg.add_edge('prod_britannia_marie', 'prod_parle_g', 'SIMILAR_TO', 0.8)
    kg.add_edge('prod_lays_classic', 'prod_lays_cream_onion', 'SIMILAR_TO', 0.95)
    kg.add_edge('prod_lays_cream_onion', 'prod_lays_classic', 'SIMILAR_TO', 0.95)
    
    return kg


# =====================================================
# STREAMLIT UI
# =====================================================

def main():
    st.set_page_config(
        page_title="Shopkeeper Assistant",
        page_icon="🏪",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 0.5rem;
        }
        .sub-header {
            font-size: 1.2rem;
            color: #6b7280;
            margin-bottom: 2rem;
        }
        .product-card {
            background-color: #f3f4f6;
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin: 1rem 0;
            border-left: 4px solid #4f46e5;
        }
        .explanation-box {
            background-color: #e0e7ff;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 1rem;
        }
        .tag {
            display: inline-block;
            background-color: #4f46e5;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            margin: 0.25rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<div class="main-header">🏪 Shopkeeper Product Substitution Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Knowledge Graph-based product recommendations using graph search and rule-based reasoning</div>', unsafe_allow_html=True)
    
    # Initialize Knowledge Graph
    if 'kg' not in st.session_state:
        st.session_state.kg = initialize_knowledge_graph()
    
    kg = st.session_state.kg
    
    # Get all products for dropdown
    all_products = [(node_id, node.data['name']) 
                    for node_id, node in kg.nodes.items() 
                    if node.type == 'product']
    all_products.sort(key=lambda x: x[1])
    
    # Sidebar - Inputs
    st.sidebar.header("🔍 Search Parameters")
    
    # Product selection
    product_options = {name: id for id, name in all_products}
    selected_product_name = st.sidebar.selectbox(
        "Select Product",
        options=list(product_options.keys()),
        help="Choose the product you're looking for"
    )
    selected_product_id = product_options[selected_product_name]
    
    # Max price
    max_price = st.sidebar.number_input(
        "Maximum Price (₹)",
        min_value=0,
        max_value=1000,
        value=0,
        step=5,
        help="Set 0 for no price limit"
    )
    max_price = max_price if max_price > 0 else None
    
    # Required tags
    available_tags = [
        'vegetarian', 'lactose_free', 'low_fat', 'low_sugar',
        'no_sugar', 'probiotic', 'full_cream', 'pasteurized',
        'toned', 'glucose', 'salty', 'spicy', 'butter_cookies'
    ]
    
    required_tags = st.sidebar.multiselect(
        "Required Attributes",
        options=available_tags,
        help="Product must have ALL selected attributes"
    )
    
    # Preferred brand
    all_brands = [(node_id, node.data['name']) 
                  for node_id, node in kg.nodes.items() 
                  if node.type == 'brand']
    all_brands.sort(key=lambda x: x[1])
    
    brand_options = {'Any Brand': None}
    brand_options.update({name: id for id, name in all_brands})
    
    preferred_brand_name = st.sidebar.selectbox(
        "Preferred Brand (Optional)",
        options=list(brand_options.keys()),
        help="Prefer products from this brand"
    )
    preferred_brand = brand_options[preferred_brand_name]
    
    # Search button
    search_button = st.sidebar.button("🔍 Find Alternatives", type="primary", use_container_width=True)
    
    # Info section in sidebar
    with st.sidebar.expander("ℹ️ How It Works"):
        st.markdown("""
        **Knowledge Graph Structure:**
        - Nodes: Products, Categories, Brands
        - Edges: IS_A, HAS_BRAND, SIMILAR_TO
        
        **Search Algorithm:**
        - BFS graph traversal
        - Multi-factor scoring system
        - Rule-based explanations
        
        **Constraints:**
        - Stock availability
        - Price limits
        - Required attributes
        """)
    
    # Main content area
    if search_button:
        with st.spinner("Searching for alternatives..."):
            product = kg.get_node(selected_product_id)
            
            if not product:
                st.error("❌ Product not found in database")
                return
            
            # Check if product is in stock
            if product.data['in_stock']:
                st.success("✅ Product Available!")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"### {product.data['name']}")
                    st.markdown(f"**Price:** ₹{product.data['price']}")
                    
                    if product.data.get('attributes'):
                        st.markdown("**Attributes:**")
                        tags_html = ''.join([f'<span class="tag">{attr}</span>' 
                                           for attr in product.data['attributes']])
                        st.markdown(tags_html, unsafe_allow_html=True)
                
                with col2:
                    st.metric("Status", "In Stock", delta="Available")
                
            else:
                st.warning(f"⚠️ **{product.data['name']}** is currently out of stock")
                st.markdown("---")
                
                # Find alternatives
                constraints = {
                    'maxPrice': max_price,
                    'requiredTags': required_tags,
                    'preferredBrand': preferred_brand
                }
                
                alternatives = kg.find_alternatives(selected_product_id, constraints)
                
                if not alternatives:
                    st.error("❌ No suitable alternatives found matching your criteria")
                    st.info("💡 Try relaxing some constraints (price limit or required attributes)")
                else:
                    st.success(f"✨ Found {len(alternatives)} Alternative(s)")
                    
                    for idx, alt in enumerate(alternatives, 1):
                        alt_product = alt['product']
                        alt_data = alt_product.data
                        
                        with st.container():
                            st.markdown(f"### Alternative {idx}")
                            
                            col1, col2, col3 = st.columns([3, 1, 1])
                            
                            with col1:
                                st.markdown(f"**{alt_data['name']}**")
                                
                                if alt_data.get('attributes'):
                                    tags_html = ''.join([f'<span class="tag">{attr}</span>' 
                                                       for attr in alt_data['attributes']])
                                    st.markdown(tags_html, unsafe_allow_html=True)
                            
                            with col2:
                                st.metric("Price", f"₹{alt_data['price']}")
                            
                            with col3:
                                st.metric("Score", f"{alt['score']:.0f}")
                            
                            # Explanations
                            explanations = kg.generate_explanation(alt, product, constraints)
                            
                            st.markdown("**📋 Why this alternative?**")
                            for exp in explanations:
                                st.markdown(f"- **[{exp['rule']}]** {exp['text']}")
                            
                            st.markdown("---")
    
    else:
        # Welcome screen
        st.info("👈 Select a product and click 'Find Alternatives' to get started")
        
        # Display some statistics
        col1, col2, col3, col4 = st.columns(4)
        
        total_products = sum(1 for n in kg.nodes.values() if n.type == 'product')
        total_categories = sum(1 for n in kg.nodes.values() if n.type == 'category')
        total_brands = sum(1 for n in kg.nodes.values() if n.type == 'brand')
        total_edges = len(kg.edges)
        
        col1.metric("Products", total_products)
        col2.metric("Categories", total_categories)
        col3.metric("Brands", total_brands)
        col4.metric("Relationships", total_edges)
        
        # Sample products display
        st.markdown("### 📦 Sample Products in Database")
        
        sample_products = list(all_products)[:6]
        cols = st.columns(3)
        
        for idx, (prod_id, prod_name) in enumerate(sample_products):
            prod_node = kg.get_node(prod_id)
            with cols[idx % 3]:
                status = "✅ In Stock" if prod_node.data['in_stock'] else "❌ Out of Stock"
                st.markdown(f"""
                <div class="product-card">
                    <strong>{prod_name}</strong><br>
                    ₹{prod_node.data['price']}<br>
                    <small>{status}</small>
                </div>
                """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
