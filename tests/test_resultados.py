"""RESULTADOS rendering: interpretation formatting and the generated README block (no warehouse needed)."""
from __future__ import annotations

import yaml

from src import resultados
from src.config import SQL_DIR


def test_note_is_inline_for_one_paragraph_and_a_list_for_several_lines():
    assert resultados.note_markdown("Una sola línea.") == "**Interpretación:** Una sola línea."
    assert resultados.note_markdown("Primera.\nSegunda.\n") == "**Interpretación:**\n\n- Primera.\n- Segunda."
    assert resultados.PENDING in resultados.note_markdown("")


def test_readme_block_is_replaced_between_markers_only():
    readme = f"# Title\n\nbefore\n\n{resultados.README_START}\nold results\n{resultados.README_END}\n\nafter\n"
    block = f"{resultados.README_START}\nnew results\n{resultados.README_END}"

    updated = resultados.replace_block(readme, block)

    assert updated == f"# Title\n\nbefore\n\n{block}\n\nafter\n"
    assert resultados.replace_block(updated, block) == updated  # idempotent
    assert resultados.replace_block("# no markers\n", block) is None


def test_interpretations_file_answers_every_question():
    data = yaml.safe_load((SQL_DIR / "interpretations.yaml").read_text(encoding="utf-8"))

    for key in ("q1", "q2", "q3", "q4", "q5"):
        assert data[key].strip() and "\n" not in data[key].strip(), key  # one paragraph each
    assert 1 <= len(data["q6"].strip().splitlines()) <= 5  # the plan allows up to 5 lines for q6
    assert data["conclusiones"].strip()
