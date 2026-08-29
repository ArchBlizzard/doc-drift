.PHONY: data eval test

data:
	uv run python eval/make_cases.py --all

eval:
	uv run python eval/run_all.py
	uv run python eval/score.py

test:
	uv run pytest
