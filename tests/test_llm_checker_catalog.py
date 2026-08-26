import sqlite3
from app.catalog.llm_checker import LLMCheckerCatalog

def test_llm_checker_catalog_adapter(tmp_path) -> None:
    path = tmp_path / "models.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE models (id TEXT, name TEXT, family TEXT, description TEXT)")
        db.execute("CREATE TABLE variants (tag TEXT, model_id TEXT, size_gb REAL, params_b REAL, quant TEXT, context_length INTEGER)")
        db.execute("INSERT INTO models VALUES ('qwen2.5', 'Qwen 2.5', 'qwen2', 'Coding model')")
        db.execute("INSERT INTO variants VALUES ('qwen2.5:3b', 'qwen2.5', 2.0, 3.0, 'Q4_K_M', 32768)")
    models = LLMCheckerCatalog(str(path)).all()
    assert len(models) == 1
    assert models[0].ollama_tag == "qwen2.5:3b"
    assert models[0].parameter_count_b == 3
    assert models[0].size_gb == 2
