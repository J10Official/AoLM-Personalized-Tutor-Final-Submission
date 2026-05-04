"""
Centralised Few-Shot Examples for all DSPy Agents.

Each agent gets 2-3 hand-crafted examples that teach the LLM the exact
format, depth calibration, and quality expected. Examples are designed
to cover the range of mastery levels and edge cases.

Also loads flywheel-approved examples from disk and merges them.
"""

import os
import json
import dspy


def _load_flywheel_examples() -> dict:
    """Load approved examples from the flywheel export, if available."""
    flywheel_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "flywheel", "approved_examples.json"
    )
    if os.path.exists(flywheel_path):
        with open(flywheel_path, "r") as f:
            return json.load(f)
    return {"doubt_resolution": [], "evaluation": []}


# ═══════════════════════════════════════════════
# Source Curator Examples
# ═══════════════════════════════════════════════

SOURCE_CURATOR_EXAMPLES = [
    dspy.Example(
        concept_name="Binary Search",
        concept_description="An efficient search algorithm that finds the position of a target value within a sorted array by repeatedly dividing the search interval in half.",
        lecture_transcript="Today we look at binary search. The idea is simple: if the array is sorted, we can compare the target with the middle element. If the target is less, we search the left half; if greater, the right half. This gives us O(log n) time complexity...",
        related_concepts_info='[{"name": "Arrays", "description": "Contiguous data structures", "relationship": "prerequisite", "learner_mastery": 0.8}]',
        mastery_level="beginner",
        depth_instructions="The learner is a beginner (mastery < 0.3). Use analogies, simple language, and first principles.",
        curated_document="""Imagine you're looking for a word in a dictionary. You don't start from page 1 — you open it roughly in the middle, check if your word comes before or after, and then repeat with the correct half.

Binary search works exactly like this, but with a sorted list of numbers (an array).

Here's the core idea:
- You need a SORTED array (numbers in order from small to large)
- Look at the middle element
- If it's your target — done!
- If your target is smaller — search only the LEFT half
- If your target is bigger — search only the RIGHT half
- Repeat until you find it or run out of elements

Why is this powerful? Each step eliminates HALF the remaining elements. With 1,000 elements, you need at most ~10 comparisons (because 2^10 = 1,024). Compare that to checking every element one by one (up to 1,000 comparisons).

Think of it like a guessing game: "I'm thinking of a number between 1 and 100." The best strategy is always to guess the middle — that's binary search.""",
        quality_notes="Beginner-calibrated: uses dictionary analogy, avoids jargon, builds from 'why' to 'what'. Transcript provided clear O(log n) explanation that was simplified into the guessing game metaphor."
    ).with_inputs("concept_name", "concept_description", "lecture_transcript", "related_concepts_info", "mastery_level", "depth_instructions"),

    dspy.Example(
        concept_name="Backpropagation",
        concept_description="The algorithm used to compute gradients in neural networks by applying the chain rule of calculus, propagating error signals from the output layer back through the network.",
        lecture_transcript="Backpropagation computes ∂L/∂w for every weight w by applying the chain rule layer by layer. Starting from the loss, we compute local gradients at each node and multiply them along each path...",
        related_concepts_info='[{"name": "Chain Rule", "description": "Derivative of composed functions", "relationship": "prerequisite", "learner_mastery": 0.85}, {"name": "Gradient Descent", "description": "Optimisation via gradient steps", "relationship": "prerequisite", "learner_mastery": 0.7}]',
        mastery_level="advanced",
        depth_instructions="The learner is advanced (mastery >= 0.6). Use full technical precision, formal definitions, and mathematical notation where applicable.",
        curated_document="""Backpropagation is the efficient computation of ∂L/∂θ for all parameters θ in a computational graph, using reverse-mode automatic differentiation (a direct application of the chain rule).

**Formal Setup:**
Given a loss function L = f(g(h(x; w₁); w₂); w₃), backpropagation computes:

∂L/∂w₃ = ∂L/∂f · ∂f/∂w₃
∂L/∂w₂ = ∂L/∂f · ∂f/∂g · ∂g/∂w₂
∂L/∂w₁ = ∂L/∂f · ∂f/∂g · ∂g/∂h · ∂h/∂w₁

**Key insight:** The chain rule factors share upstream gradients. By caching intermediate results in the forward pass and reusing upstream gradients in the backward pass, backpropagation achieves O(n) complexity — the same order as the forward pass itself.

**Vanishing/Exploding Gradients:**
When many layers have Jacobians with singular values < 1 (or > 1), the product of gradients shrinks (or grows) exponentially. Mitigation strategies include: residual connections (additive skip paths), batch normalisation, careful weight initialisation (Xavier/He), and gradient clipping.

**Computational Graph Perspective:**
Each node stores its local Jacobian ∂output/∂input. The backward pass is a reverse topological traversal, accumulating gradients via the chain rule at each junction. This is mathematically equivalent to reverse-mode AD.""",
        quality_notes="Advanced-calibrated: full mathematical notation, formal definitions, discusses edge cases (vanishing gradients), connects to computational graph theory. Transcript's chain rule explanation was expanded with proper notation."
    ).with_inputs("concept_name", "concept_description", "lecture_transcript", "related_concepts_info", "mastery_level", "depth_instructions"),
]


# ═══════════════════════════════════════════════
# Learning Curator Examples
# ═══════════════════════════════════════════════

LEARNING_CURATOR_EXAMPLES = [
    dspy.Example(
        concept_name="Recursion",
        concept_description="A programming technique where a function calls itself to solve smaller subproblems of the same type.",
        mastery_level="beginner",
        depth_instructions="Beginner level (mastery < 0.3): Use analogies and first principles. Explain concepts using everyday language.",
        known_concepts="Variables, Functions, Conditionals",
        source_material="Recursion is when a function calls itself. Every recursive function needs a base case to stop the recursion, and a recursive case that breaks the problem into a smaller version of itself.",
        global_doubts='["Why doesn\'t recursion run forever?", "What is a base case?"]',
        user_personal_graph='{"variables": {"name": "Variables", "mastery": 0.8}, "functions": {"name": "Functions", "mastery": 0.6}, "conditionals": {"name": "Conditionals", "mastery": 0.5}}',
        explanation="""Think of recursion like Russian nesting dolls (matryoshka dolls). To open the biggest doll, you find a smaller doll inside. To open that one, there's an even smaller doll. You keep going until you reach the tiniest doll that doesn't open — that's your BASE CASE.

In programming, recursion works the same way:
1. A function calls ITSELF, but with a slightly SMALLER problem
2. Eventually, the problem gets so small that you know the answer directly — that's the base case
3. Then the answers "bubble back up" through all the function calls

**Example with factorial:**
- factorial(4) = 4 × factorial(3)
- factorial(3) = 3 × factorial(2)
- factorial(2) = 2 × factorial(1)
- factorial(1) = 1 ← BASE CASE (we just know this!)
- Now bubble up: 2×1=2, 3×2=6, 4×6=24

You already know functions (calling a block of code) and conditionals (if/else). Recursion just combines these: the function uses an if/else to decide whether to return the base case or call itself again.

The critical rule: EVERY recursive function MUST have a base case, or it WILL run forever (until your computer runs out of memory — called a "stack overflow").""",
        anticipated_doubts='["How does the computer keep track of all those nested function calls?", "When should I use recursion instead of a loop?", "What happens if I forget the base case?"]',
        key_takeaways='["Recursion = a function that calls itself with a smaller problem", "Every recursive function needs a base case to stop", "Without a base case, recursion causes a stack overflow", "Think of it like nesting dolls — each layer is a smaller version of the same problem"]'
    ).with_inputs("concept_name", "concept_description", "mastery_level", "depth_instructions", "known_concepts", "source_material", "global_doubts", "user_personal_graph"),
]


# ═══════════════════════════════════════════════
# Retrieval Question Examples
# ═══════════════════════════════════════════════

RETRIEVAL_QUESTION_EXAMPLES = [
    dspy.Example(
        prerequisite_concepts='[{"name": "Arrays", "description": "Ordered collection of elements accessible by index"}, {"name": "Comparison Operators", "description": "Operators like <, >, == that compare values"}]',
        target_concept="Binary Search",
        retrieval_questions='[{"question": "Without looking anything up: how would you access the 5th element in an array?", "concept": "Arrays", "expected_answer": "Use index 4 (since arrays are 0-indexed), e.g. arr[4]"}, {"question": "If x = 7 and y = 12, what does x < y evaluate to?", "concept": "Comparison Operators", "expected_answer": "True, because 7 is less than 12"}, {"question": "Why does the ORDER of elements in an array matter for searching?", "concept": "Arrays", "expected_answer": "If elements are sorted/ordered, we can use more efficient search strategies like binary search instead of checking every element"}]'
    ).with_inputs("prerequisite_concepts", "target_concept"),
]


# ═══════════════════════════════════════════════
# Doubt Resolver Examples
# ═══════════════════════════════════════════════

DOUBT_RESOLVER_EXAMPLES = [
    # Example 1: Misconception detected
    dspy.Example(
        doubt="Isn't recursion just the same as a for loop? They both repeat things.",
        concept_name="Recursion",
        concept_description="A programming technique where a function calls itself to solve smaller subproblems.",
        transcript_context="Recursion differs from iteration in that each recursive call creates a new stack frame with its own local variables...",
        known_concepts='[{"name": "For Loops", "description": "Iterating over a sequence", "mastery": 0.7}, {"name": "Functions", "description": "Reusable blocks of code", "mastery": 0.6}]',
        mastery_level="beginner",
        depth_instructions="Beginner level: Answer using simple analogies and first principles.",
        answer="""Great question! They seem similar because both involve repetition, but they work in fundamentally different ways.

Think of it like this: A for loop is like walking down a straight hallway, opening each door one by one. You always know where you are and where you're going next.

Recursion is more like standing between two mirrors — each reflection contains another reflection. The function creates a COPY of itself, and each copy works on a smaller piece of the problem.

Key differences you can relate to what you already know:
- A for loop (which you know well!) keeps going in ONE direction. It uses a counter variable that changes.
- Recursion goes DEEPER — each function call waits for the next one to finish before it can continue. It's like stacking function calls on top of each other.

The biggest practical difference: recursion naturally handles problems that have a NESTED structure (like folders inside folders, or trees), where a loop would be awkward to write.""",
        misconception_type="relational",
        misconception_explanation="The learner conflates iteration and recursion because both involve repetition. The misconception is relational: they see the surface similarity (repetition) but miss the structural difference (iteration is linear traversal; recursion is self-similar decomposition with a call stack).",
        follow_up_question="Can you think of a real-world example where something contains a smaller version of itself? How would that be hard to handle with a simple for loop?"
    ).with_inputs("doubt", "concept_name", "concept_description", "transcript_context", "known_concepts", "mastery_level", "depth_instructions"),

    # Example 2: No misconception
    dspy.Example(
        doubt="What happens to memory when recursion goes very deep?",
        concept_name="Recursion",
        concept_description="A programming technique where a function calls itself to solve smaller subproblems.",
        transcript_context="Each recursive call adds a frame to the call stack. The stack has limited memory, so excessively deep recursion causes a stack overflow error...",
        known_concepts='[{"name": "Functions", "description": "Reusable blocks of code", "mastery": 0.7}, {"name": "Variables", "description": "Named storage locations", "mastery": 0.8}]',
        mastery_level="intermediate",
        depth_instructions="Intermediate level: Mix intuition with technical precision.",
        answer="""Each time a recursive function calls itself, the computer allocates a new "stack frame" — think of it as a sticky note where the function writes down its local variables and where to return to.

These sticky notes pile up on the "call stack" (a region of memory). Since you understand variables, each frame stores its own copy of any local variables.

For example, in factorial(1000), there would be 1000 stack frames, each holding its own value of n.

The problem: the call stack has a FIXED SIZE (typically 1-8 MB depending on the language/OS). If recursion goes too deep, you run out of space and get a "Stack Overflow Error."

Practical limits:
- Python: default recursion limit is 1,000 calls (configurable with sys.setrecursionlimit)
- Java/C: typically ~10,000-50,000 frames before overflow

This is why some problems that COULD be recursive are better solved iteratively for very large inputs — or using "tail recursion" which some compilers can optimise into a loop.""",
        misconception_type="none",
        misconception_explanation="No misconception detected.",
        follow_up_question="If Python's default recursion limit is 1,000, how would you compute factorial(5000) without hitting the limit?"
    ).with_inputs("doubt", "concept_name", "concept_description", "transcript_context", "known_concepts", "mastery_level", "depth_instructions"),
]


# ═══════════════════════════════════════════════
# Question Generator Examples
# ═══════════════════════════════════════════════

QUESTION_GENERATOR_EXAMPLES = [
    # Low mastery — remember/understand questions
    dspy.Example(
        concept_name="Hash Tables",
        concept_description="A data structure that maps keys to values using a hash function for O(1) average-case lookup.",
        transcript_context="A hash table uses a hash function to compute an index. Collisions are handled by chaining or open addressing...",
        mastery_level="beginner",
        depth_instructions="Beginner (mastery < 0.3): Focus on recall and basic understanding.",
        bloom_levels_allowed="remember, understand",
        known_concepts_for_interleaving='[{"name": "Arrays", "description": "Ordered collection of elements accessible by index"}]',
        past_doubts='["Why do we need hash tables when we already have arrays?"]',
        user_personal_graph='{"arrays": {"name": "Arrays", "mastery": 0.7}}',
        questions="""[
  {"question": "What is the primary purpose of a hash function in a hash table?", "type": "mcq", "bloom_level": "remember", "interleaved_concept": null, "pattern": "property_transfer", "options": ["To sort the data", "To compute an index from a key", "To encrypt the data", "To compress the data"], "correct_answer": "To compute an index from a key", "rubric": null},
  {"question": "What happens when two different keys produce the same hash value?", "type": "mcq", "bloom_level": "understand", "interleaved_concept": null, "pattern": "failure_mode", "options": ["The second key is rejected", "A collision occurs and must be resolved", "The hash table is rebuilt", "The first key is overwritten"], "correct_answer": "A collision occurs and must be resolved", "rubric": null},
  {"question": "In your own words, explain why hash tables provide faster lookups than arrays when searching by value (not by index).", "type": "written", "bloom_level": "understand", "interleaved_concept": "Arrays", "pattern": "mechanism_contrast", "options": null, "correct_answer": "Arrays require scanning each element (O(n)) when searching by value. Hash tables use a hash function to jump directly to the right location (O(1) average).", "rubric": "Should contrast linear scan in arrays with direct access in hash tables. Mention O(n) vs O(1)."},
  {"question": "If you have an array of 1 million names and need to check if 'Alice' is in it, how would a hash table be faster than searching the array?", "type": "written", "bloom_level": "understand", "interleaved_concept": "Arrays", "pattern": "mechanism_contrast", "options": null, "correct_answer": "With an array, you might need to check all 1 million entries. With a hash table, you compute hash('Alice') to get the index directly — one step instead of up to a million.", "rubric": "Should explain that hash table avoids scanning by computing the index directly."},
  {"question": "A student says: 'Hash tables are just arrays with extra steps.' Is this a fair description? Why or why not?", "type": "written", "bloom_level": "understand", "interleaved_concept": "Arrays", "pattern": "misconception_probe", "options": null, "correct_answer": "Partially fair: hash tables DO use an array internally. But the 'extra step' (the hash function) is what enables O(1) key-based lookup, which is fundamentally different from array index-based access.", "rubric": "Should acknowledge the array foundation but explain the hash function adds a key-to-index mapping that changes the access pattern."}
]"""
    ).with_inputs("concept_name", "concept_description", "transcript_context", "mastery_level", "depth_instructions", "bloom_levels_allowed", "known_concepts_for_interleaving", "past_doubts", "user_personal_graph"),
]


# ═══════════════════════════════════════════════
# Evaluator Examples (Written)
# ═══════════════════════════════════════════════

EVALUATOR_WRITTEN_EXAMPLES = [
    # Strong answer
    dspy.Example(
        question="Explain why hash tables provide O(1) average-case lookup, and describe what can cause this to degrade.",
        correct_answer="Hash tables use a hash function to compute an array index from a key, allowing direct access. Degradation occurs when many keys hash to the same index (collisions), causing chains/probes that approach O(n).",
        rubric="Should explain hash function → index mapping, mention collision as cause of degradation, and note worst-case O(n).",
        student_answer="Hash tables use a hash function to convert the key into an index, so you can jump directly to the value without scanning. The average case is O(1) because the hash function distributes keys evenly across the array. However, if many keys collide (map to the same index), the lookup degrades because you have to traverse a chain (linked list) at that index. In the worst case, all keys collide and lookup becomes O(n).",
        concept_name="Hash Tables",
        concept_accuracy_score=3,
        reasoning_score=2,
        example_score=1,
        precision_score=1,
        connection_score=2,
        feedback="Excellent answer. You correctly explained the hash function → index mapping mechanism and accurately described collision as the cause of O(1) degradation to O(n). Your mention of chaining shows understanding of collision resolution. To earn full marks on examples, you could provide a concrete scenario (e.g., 'if all keys are multiples of the table size')."
    ).with_inputs("question", "correct_answer", "rubric", "student_answer", "concept_name"),

    # Weak answer
    dspy.Example(
        question="Explain why hash tables provide O(1) average-case lookup, and describe what can cause this to degrade.",
        correct_answer="Hash tables use a hash function to compute an array index from a key, allowing direct access. Degradation occurs when many keys hash to the same index (collisions), causing chains/probes that approach O(n).",
        rubric="Should explain hash function → index mapping, mention collision as cause of degradation, and note worst-case O(n).",
        student_answer="Hash tables are fast because they use hashing. They can get slow sometimes.",
        concept_name="Hash Tables",
        concept_accuracy_score=1,
        reasoning_score=0,
        example_score=0,
        precision_score=0,
        connection_score=0,
        feedback="Your answer shows awareness that hashing is involved, but it's too vague to demonstrate understanding. Specifically: (1) HOW does hashing make lookups fast? Explain that the hash function converts a key into an array index for direct access. (2) WHAT causes slowness? Explain that collisions — when multiple keys hash to the same index — force the table to search through a chain, degrading from O(1) to O(n). Try to be specific about the mechanism, not just the result."
    ).with_inputs("question", "correct_answer", "rubric", "student_answer", "concept_name"),
]


# ═══════════════════════════════════════════════
# Evaluator Examples (MCQ)
# ═══════════════════════════════════════════════

EVALUATOR_MCQ_EXAMPLES = [
    dspy.Example(
        question="What is the average time complexity of lookup in a hash table?",
        correct_answer="O(1)",
        student_answer="O(1)",
        is_correct=True,
        feedback="Correct! Hash tables provide O(1) average-case lookup because the hash function computes the index directly."
    ).with_inputs("question", "correct_answer", "student_answer"),

    dspy.Example(
        question="What is the average time complexity of lookup in a hash table?",
        correct_answer="O(1)",
        student_answer="O(n)",
        is_correct=False,
        feedback="Incorrect. O(n) is the WORST case (when all keys collide). The average case is O(1) because the hash function distributes keys across the array, giving direct access to each bucket."
    ).with_inputs("question", "correct_answer", "student_answer"),
]


# ═══════════════════════════════════════════════
# Loader: merge hand-crafted + flywheel examples
# ═══════════════════════════════════════════════

def get_all_examples() -> dict:
    """
    Return all examples (hand-crafted + flywheel-approved) grouped by agent.

    Returns dict with keys:
        source_curator, learning_curator, retrieval_questions,
        doubt_resolver, question_generator, evaluator_written, evaluator_mcq
    """
    flywheel = _load_flywheel_examples()

    # Convert flywheel doubt examples to DSPy Example format
    flywheel_doubt_examples = []
    for ex in flywheel.get("doubt_resolution", [])[:5]:  # Max 5 from flywheel
        try:
            flywheel_doubt_examples.append(
                dspy.Example(
                    doubt=ex["doubt"],
                    concept_name=ex["concept_name"],
                    concept_description="",
                    transcript_context="",
                    known_concepts="[]",
                    mastery_level="intermediate",
                    depth_instructions="",
                    answer=ex["answer"],
                    misconception_type=ex.get("misconception_type", "none"),
                    misconception_explanation=ex.get("misconception_explanation", ""),
                    follow_up_question=ex.get("follow_up_question", ""),
                ).with_inputs("doubt", "concept_name", "concept_description", "transcript_context", "known_concepts", "mastery_level", "depth_instructions")
            )
        except Exception:
            continue

    return {
        "source_curator": SOURCE_CURATOR_EXAMPLES,
        "learning_curator": LEARNING_CURATOR_EXAMPLES,
        "retrieval_questions": RETRIEVAL_QUESTION_EXAMPLES,
        "doubt_resolver": DOUBT_RESOLVER_EXAMPLES + flywheel_doubt_examples,
        "question_generator": QUESTION_GENERATOR_EXAMPLES,
        "evaluator_written": EVALUATOR_WRITTEN_EXAMPLES,
        "evaluator_mcq": EVALUATOR_MCQ_EXAMPLES,
    }
