"""把 e2m2e 工具的 input_schema 导出为前端静态 JSON。

用法：``uv run python tools/export_tool_schemas.py``
产物：``frontend/src/toolSchemas/<tool>.json``。升级 e2m2e 后重跑。

GUI 参数面板从 schema 自动生成表单。schema 是构建期资产而非运行期查询：
sidecar 协议没有 schema 元工具，且 schema 变化本就应当随版本评审，
不宜静默热取。
"""

import json
from pathlib import Path

from e2m2e.api.facade import Facade
from e2m2e.api.mcp import tools


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "frontend" / "src" / "toolSchemas"
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in tools.tool_specs(Facade()):
        path = out_dir / f"{spec.name}.json"
        path.write_text(json.dumps(spec.input_schema, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{spec.name}: {path.name}")


if __name__ == "__main__":
    main()