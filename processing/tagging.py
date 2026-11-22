"""Simple topic tagging: predefined topic matching + frequent keywords."""
import re
from collections import Counter

TOPICS = {
    "Data Structures": ["array", "linked list", "stack", "queue", "tree", "binary tree", "bst",
        "graph", "heap", "hashing", "hash table", "linear data structure", "lifo", "fifo",
        "insertion", "deletion", "traversal", "circular queue", "priority queue"],
    "Algorithms": ["binary search", "linear search", "searching algorithm", "sorting", "bubble sort",
        "merge sort", "quick sort", "insertion sort", "selection sort", "recursion", "dynamic programming",
        "greedy", "time complexity", "space complexity", "big o", "sorted array", "divide and conquer"],
    "Operating Systems": ["process", "thread", "deadlock", "process scheduling", "scheduling", "semaphore",
        "mutex", "paging", "segmentation", "virtual memory", "round robin", "fcfs", "context switch",
        "race condition", "critical section", "kernel"],
    "DBMS": ["normalization", "sql", "primary key", "foreign key", "er diagram", "transaction", "acid",
        "join", "index", "relational", "schema", "2nf", "3nf", "bcnf", "query"],
    "Computer Networks": ["osi model", "tcp", "udp", "ip address", "routing", "router", "switch",
        "http", "dns", "subnet", "protocol", "ethernet", "firewall", "bandwidth"],
    "Mathematics": ["matrix", "determinant", "eigenvalue", "integration", "differentiation", "derivative",
        "probability", "limit", "vector", "laplace", "fourier", "series", "theorem"],
    "COA": ["cpu", "alu", "register", "cache", "pipeline", "instruction set", "memory hierarchy",
        "addressing mode", "bus", "microprogram"],
}
ACRONYMS = {"lifo", "fifo", "bst", "sql", "tcp", "udp", "dns", "cpu", "alu", "http", "acid", "bcnf", "2nf", "3nf"}
STOP = set("""the a an and or of to in is are was were be been it its this that for on with as by at from
which can will has have had not but if then than so such these those into also each other more most
used using use called known may""".split())


def generate_tags(text, limit=8):
    low = re.sub(r"\s+", " ", text.lower())
    found = []
    for words in TOPICS.values():
        for w in words:
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"s?(?![a-z0-9])", low):
                found.append(w)
    found = sorted(set(found), key=lambda w: -len(w))
    tags = [w.upper() if w in ACRONYMS else w.title() for w in found]
    if len(tags) < limit:
        words = [w for w in re.findall(r"[a-z]{5,}", low) if w not in STOP]
        have = " ".join(found)
        for w, _ in Counter(words).most_common(12):
            if w not in have and w.title() not in tags and Counter(words)[w] >= 2:
                tags.append(w.title())
    return tags[:limit]
