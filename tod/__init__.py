"""Transfer Orbit Design 脚本包。

本包用于组织相关模块的导入边界，不在导入时执行数值计算。
"""

# 兜底安装 e2m2e 旧路径兼容别名：任何先于 tod.commons.constants 的 `import tod`
# 都会在这里把旧路径模块装好（install 幂等，重复调用安全）。
from tod.commons import e2m2e_compat as _e2m2e_compat

_e2m2e_compat.install()


