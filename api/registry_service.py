"""脚本注册表 API — 返回所有脚本元数据和参数定义"""
from fastapi import APIRouter

from api.models import (
    ScriptSchema,
    EnvParamSchema,
    CliParamSchema,
    UnitGroup,
    UnitOption,
)

router = APIRouter()


def _convert_env_param(p) -> EnvParamSchema:
    return EnvParamSchema(
        env_var=p.env_var,
        label=p.label,
        file_category=p.file_category,
        file_type=p.file_type,
    )


def _convert_cli_param(p) -> CliParamSchema:
    return CliParamSchema(
        flag=p.flag,
        label=p.label,
        param_type=p.param_type,
        default=p.default,
        help=p.help,
        file_category=p.file_category,
        unit_group=p.unit_group,
        advanced=p.advanced,
    )


def _convert_script(e) -> ScriptSchema:
    return ScriptSchema(
        module=e.module,
        name=e.name,
        description=e.description,
        script_path=e.script_path,
        output_dir=e.output_dir,
        accepts_file_arg=e.accepts_file_arg,
        needs_spice=e.needs_spice,
        env_params={
            k: _convert_env_param(v) for k, v in e.env_params.items()
        },
        cli_params=[_convert_cli_param(p) for p in e.cli_params],
    )


@router.get("/scripts")
async def get_scripts():
    """返回所有脚本，按分类组织"""
    from scripts.gui.script_registry import SCRIPTS, UNIT_GROUPS

    result = {}
    for category, entries in SCRIPTS.items():
        result[category] = [_convert_script(e) for e in entries]

    unit_groups = {}
    for group_name, units in UNIT_GROUPS.items():
        unit_groups[group_name] = UnitGroup(
            name=group_name,
            units=[UnitOption(name=u_name, factor=u_factor) for u_name, u_factor in units.items()],
        )

    return {"scripts": result, "unit_groups": unit_groups}
