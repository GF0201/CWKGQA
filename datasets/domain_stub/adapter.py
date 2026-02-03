"""Stub adapter: returns dummy samples for smoke test."""


def get_dummy_samples(n: int = 5) -> list[dict]:
    return [
        {"id": f"stub_{i}", "question": f"Dummy question {i}?", "answers": [f"A{i}"]}
        for i in range(n)
    ]
