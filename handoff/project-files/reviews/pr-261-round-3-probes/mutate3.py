"""Round 3, batch 3: F7 redone (the batch-1 mutant was an IndentationError)."""
import sys
from pathlib import Path
sys.path.insert(0, "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-261-r3")
import mutate as m

m.MUT = m.SP / "r3-261-mut3"
m.ENG = m.MUT / "engine"
m.MUTATIONS = [
    ("F7' no window problem", "engine/extract/ai.py", '            found.append("no window start")\n', "            pass\n", ["tests/test_ai.py", "tests/test_batch.py", "tests/test_score.py"]),
]
m.main()
