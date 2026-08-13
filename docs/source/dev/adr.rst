# 架构决策记录（ADR）

架构决策记录（Architecture Decision Record）逐项记录项目的关键架构决策：
背景、决策、后果。编号越大越新。以下列表按编号排列，全文见对应页面。

.. toctree::
   :maxdepth: 1

   adr-0013-ephemeris-visualization-conventions
   adr-0012-defer-gil-and-facade-to-upstream
   adr-0011-algorithm-layer-direct-call
   adr-0010-embedded-visualization
   adr-0009-autogen-params-from-pydantic
   adr-0008-output-as-persistence
   adr-0007-big-bang-gui-replacement
   adr-0006-e2m2e-gui-frontend
   adr-0005-script-registration-consolidation
   adr-0004-job-status-dispatch-result
   adr-0003-run-preflight-confirmation
   adr-0002-dro-catalog-seed-gui-v1
   adr-0001-ui-i18n-zh-en

## 阅读指引

- **当前架构**以 :doc:`architecture` 为准；ADR 记录决策的**历史语境**，
  两者不一致时以架构文档为准。
- ADR-0001 至 0005 记录旧 GUI（`tod/gui/`）时代的决策，相关机制
  （ScriptEntry 脚本注册、JobStatus、运行前确认弹窗）已随 ADR-0007 的
  大爆炸替换废弃，仅作历史参考。
- ADR-0006 起为现行 GUI 的决策：e2m2e 前端定位（0006）、大爆炸替换
  （0007）、output/ 持久化（0008）、Pydantic 自动参数面板（0009）、
  内嵌可视化（0010）、算法层直调（0011）、卡顿与接口边界依赖上游
  （0012）、星历可视化坐标与时间约定（0013）。
