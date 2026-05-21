# PRD: 重设计 DRO/Halo 星历转换脚本

## Problem Statement

当前星历转换脚本只能覆盖部分流程：已有单条 **DRO** 转星历与单条 **Halo** 转星历脚本，但两者主体流程重复、参数多处硬编码，并且缺少 **轨道族转换** 的一等入口。用户需要重新设计星历转换能力，使同一套转换语义明确支持四个场景：单条 DRO、DRO 轨道族、单条 Halo、Halo 轨道族。

现有脚本还存在可复现性问题：输入文件、参考历元、校正方法、patch points、SPICE kernel 目录等关键参数部分依赖硬编码或环境变量。对于星历模型转换，这些参数直接影响结果，应该通过清晰的脚本入口显式表达。

## Solution

重设计星历转换脚本为“四个薄入口 + 一个共享核心模块”的结构：

1. 保留并重构单条 DRO 转星历脚本。
2. 保留并重构单条 Halo 转星历脚本。
3. 新增 DRO **轨道族转换**脚本。
4. 新增 Halo **轨道族转换**脚本。
5. 抽取共享核心模块，封装输入加载、patch point 采样、synodic 到 J2000 转换、星历模型校正、连续性验证和 JSON 输出构建。

四个脚本都要求用户显式提供 **星历转换输入文件** 和 **参考历元**，都支持选择 **星历转换方法**，默认使用 `two_level`，默认 patch points 数量为 10。**轨道族转换**按族文件中的顺序逐条独立转换每条 **单条轨道**；默认遇到单条失败时记录失败并继续，用户可启用快速失败。

## User Stories

1. As a mission design engineer, I want to convert a single DRO from CR3BP to the ephemeris model, so that I can analyze that orbit under a higher-fidelity dynamical model
2. As a mission design engineer, I want to convert a DRO orbit family from CR3BP to the ephemeris model, so that I can compare high-fidelity behavior across the full family
3. As a mission design engineer, I want to convert a single Halo orbit from CR3BP to the ephemeris model, so that I can use the corrected trajectory in downstream high-fidelity studies
4. As a mission design engineer, I want to convert a Halo orbit family from CR3BP to the ephemeris model, so that I can evaluate a range of Halo orbits under the same ephemeris assumptions
5. As a script user, I want four explicit scripts for the four supported conversion scenarios, so that I can run the correct workflow without remembering a combined mode matrix
6. As a script user, I want the four scripts to share one core implementation, so that behavior stays consistent across DRO, Halo, single-orbit, and family workflows
7. As a script user, I want every conversion script to require `--input-file`, so that the conversion result is tied to an explicit source file
8. As a script user, I want every conversion script to require `--reference-epoch`, so that the CR3BP-to-J2000 mapping is explicit and reproducible
9. As a script user, I want single-orbit scripts to accept a single-orbit JSON file, so that existing generated single-orbit outputs remain usable
10. As a script user, I want single-orbit scripts to accept a family JSON file with `--orbit-index`, so that I can convert one selected orbit from a family output
11. As a script user, I want family scripts to require a family JSON file with `orbits`, so that the script does not silently treat a single orbit as a family
12. As a script user, I want every conversion script to support `--method standard|two_level`, so that I can choose the correction method appropriate for my run
13. As a script user, I want all scripts to default to `two_level`, so that the default path emphasizes position and velocity continuity
14. As a script user, I want every conversion script to support `--patch-points`, so that I can tune the multiple-shooting discretization
15. As a script user, I want all scripts to default to 10 patch points, so that behavior is consistent across DRO and Halo workflows
16. As a script user, I want every conversion script to support `--position-tol`, so that I can control the position continuity tolerance
17. As a script user, I want every conversion script to support `--velocity-tol`, so that I can control the velocity continuity tolerance for `two_level` correction
18. As a script user, I want every conversion script to support `--spice-kernel-dir`, so that I can run the workflow outside the default local kernel layout
19. As a script user, I want the scripts to keep a sensible default SPICE kernel directory, so that local interactive usage remains convenient
20. As a script user, I want every conversion script to support `--bodies`, so that I can override the default ephemeris body set when needed
21. As a script user, I want the default body set to remain `EARTH,MOON,SUN`, so that current Earth-Moon-Sun workflows remain convenient
22. As a script user, I want single-orbit output to include the full propagated trajectory by default, so that I can immediately plot or inspect the corrected orbit
23. As a script user, I want family conversion output to be lightweight by default, so that a large orbit family does not produce an unnecessarily huge JSON file
24. As a script user, I want family conversion to optionally include full trajectories, so that I can request complete data when file size is acceptable
25. As a script user, I want family conversion to produce one **轨道族转换结果** JSON file, so that I can consume the result as a single artifact
26. As a script user, I want the family result to include per-orbit success and failure entries, so that I can identify which family members converted successfully
27. As a script user, I want family conversion to continue after one orbit fails by default, so that a long family run still produces useful partial results
28. As a script user, I want a `--fail-fast` option for family conversion, so that strict automation can stop on the first failure
29. As a script user, I want optional family-level parallelism, so that I can speed up large family conversions when my environment supports it
30. As a script user, I want family conversion to default to serial processing, so that SPICE and nested multiple-shooting workers do not overload local resources unexpectedly
31. As a script user, I want to configure per-orbit correction workers separately from family-level workers, so that I can control total parallelism
32. As a script user, I want output files to default into `output/ephemeris`, so that generated ephemeris artifacts remain grouped together
33. As a script user, I want an `--output-file` override, so that automation can write deterministic artifact paths
34. As a downstream data consumer, I want output JSON to include source metadata, so that I can trace a result back to the input file, orbit index, orbit type, method, epoch, body set, tolerances, and patch point count
35. As a downstream data consumer, I want standard and two-level correction results normalized into a common result shape, so that downstream code does not need solver-specific parsing
36. As a downstream data consumer, I want `two_level` results to include velocity residual diagnostics, so that I can evaluate velocity continuity
37. As a downstream data consumer, I want `standard` results to omit or null velocity residual diagnostics rather than fabricating them, so that the output accurately reflects the solver behavior
38. As a developer, I want a deep module for conversion orchestration, so that the heavy workflow can be tested without duplicating four script bodies
39. As a developer, I want argument parsing to remain thin and explicit in each script, so that CLI behavior is easy to inspect
40. As a developer, I want the shared module to validate input shape before running SPICE or correction, so that user errors fail early with clear messages
41. As a developer, I want tests for family failure handling, so that a single bad orbit does not accidentally abort a default family run
42. As a developer, I want tests for single-orbit selection from a family file, so that `--orbit-index` behavior stays stable
43. As a developer, I want tests for output shape, so that downstream plotting and analysis code can rely on stable JSON contracts
44. As a developer, I want integration tests that remain optional for real SPICE/e2m2e runs, so that CI can run fast tests without local kernels
45. As a researcher, I want the scripts to avoid implicit latest file selection, so that published results can be reproduced from the recorded command
46. As a researcher, I want the same terminology for **单条轨道**, **轨道族**, **轨道族转换**, **星历转换输入文件**, **星历转换方法**, and **参考历元**, so that scripts, tests, and documentation describe the same concepts

## Implementation Decisions

- Provide four user-facing scripts rather than one combined CLI.
- Keep the existing single-orbit script naming pattern and add family-specific scripts using the same naming style.
- Implement a shared deep module that owns the conversion pipeline. The four scripts should be thin wrappers responsible for argument parsing and invoking the shared module.
- The shared module should expose a small, stable interface for loading a **单条轨道**, loading a selected **单条轨道** from a **轨道族** by index, loading all orbits from a **轨道族**, running one conversion, running **轨道族转换**, validating continuity, normalizing solver diagnostics, and constructing serializable output payloads.
- A **单条轨道** input is a CR3BP orbit object represented by top-level `states`, `times`, and `period` fields.
- A **轨道族** input is a JSON file with a top-level `orbits` list.
- Single-orbit scripts support both single-orbit files and family files with an explicit `--orbit-index`.
- Single-orbit scripts should not silently take index 0 from a family file when `--orbit-index` is omitted.
- Family scripts require a family file and process every orbit in the top-level `orbits` list.
- **轨道族转换** means converting every orbit independently. It does not mean using the previous corrected ephemeris solution as the next orbit’s initial guess.
- The default correction method is `two_level` for all four scripts.
- All scripts support `--method standard|two_level`.
- The default patch point count is 10 for all four scripts.
- All scripts support `--patch-points`.
- All scripts require `--reference-epoch`; no script should hide a fixed default reference epoch.
- All scripts require `--input-file`; no script should auto-select the newest file in an output directory.
- All scripts default to the existing local SPICE kernel directory convention and support `--spice-kernel-dir` override.
- All scripts default to `EARTH,MOON,SUN` and support `--bodies` override.
- All scripts support position tolerance and velocity tolerance options, defaulting to `1e-3 km` and `1e-6 km/s` respectively.
- Position continuity is always verified.
- Velocity continuity is included in diagnostics and pass/fail criteria when the selected method is `two_level`.
- `standard` correction should not synthesize velocity residuals if the solver result does not provide them.
- Family conversion defaults to serial processing.
- Family conversion supports optional family-level parallelism through a dedicated family worker option.
- Per-orbit correction workers remain configurable separately from family workers.
- Family conversion defaults to recording failures and continuing with subsequent orbits.
- Family conversion supports a `--fail-fast` option.
- Single-orbit output includes full propagated trajectory data by default.
- Family output is lightweight by default and includes corrected patch states/times plus diagnostics for each orbit.
- Family output supports an option to include full propagated trajectories per orbit.
- Family conversion writes one **轨道族转换结果** JSON file rather than one output file per orbit.
- Output defaults to `output/ephemeris` and supports `--output-file` override.
- Output metadata should include enough information to reproduce the conversion: source path, orbit type, mode, orbit index when applicable, method, reference epoch, body set, patch point count, tolerances, worker configuration, and timestamp.
- Failed family entries should include orbit index, source summary when available, status, and an error message.
- Successful entries should include convergence status, iteration count, residual history, final residuals, corrected patch states, corrected patch times, continuity errors, and optional full trajectory arrays.
- Existing solver dispatch normalization should be preserved and extended rather than duplicated in each script.
- Existing environment-variable-only behavior for input and method selection should be replaced by explicit CLI parameters for the redesigned scripts.
- The project domain glossary should use the resolved terms: **单条轨道**, **轨道族**, **轨道族转换**, **轨道族转换结果**, **星历转换输入文件**, **星历转换方法**, and **参考历元**.

## Testing Decisions

- Tests should focus on external behavior and stable contracts: CLI parsing, input validation, orbit selection, conversion orchestration calls, failure handling, and output JSON shape.
- Tests should avoid asserting private implementation details of the shared module beyond its public interface.
- Unit tests are preferred for this PRD. Heavy SPICE/e2m2e execution should be mocked unless explicitly marked as integration or SPICE-dependent.
- Add tests for all four script imports and argument parsing.
- Add tests that `--input-file` and `--reference-epoch` are required.
- Add tests that `--method` accepts `standard` and `two_level`, defaults to `two_level`, and rejects unsupported values.
- Add tests that `--patch-points` defaults to 10 and can be overridden.
- Add tests that tolerance defaults are `1e-3 km` and `1e-6 km/s` and can be overridden.
- Add tests that `--bodies` defaults to `EARTH,MOON,SUN` and parses overrides into the expected body list.
- Add tests that `--spice-kernel-dir` uses the default when omitted and respects overrides.
- Add tests for loading a single-orbit file.
- Add tests for rejecting a family file in a single-orbit script when `--orbit-index` is omitted.
- Add tests for selecting the correct orbit from a family file when `--orbit-index` is provided.
- Add tests for rejecting out-of-range orbit indices.
- Add tests for rejecting a single-orbit file in a family script.
- Add tests for family conversion iterating every orbit independently.
- Add tests for default family failure handling: failed entries are recorded and later orbits still run.
- Add tests for `--fail-fast`: processing stops on the first failed orbit.
- Add tests for family output defaulting to lightweight payloads without full trajectory arrays.
- Add tests for family output including full trajectory arrays when the include-full-trajectory option is enabled.
- Add tests for single-orbit output including full trajectory arrays by default.
- Add tests for output metadata and per-orbit result fields.
- Add tests for `standard` correction output not requiring velocity residual fields.
- Add tests for `two_level` correction output including velocity residual diagnostics.
- Add tests for continuity validation using mocked propagation results.
- Existing prior art includes mocked e2m2e/SPICE tests for ephemeris correction, solver dispatch tests for the correction helper, and optional SPICE-marked integration tests for Halo ephemeris conversion.
- Optional integration tests may remain marked with the existing SPICE/slow marker pattern and should not be required for fast local or CI runs.

## Out of Scope

- Designing a new correction algorithm beyond the existing `standard` and `two_level` methods.
- Implementing along-family continuation or using one corrected family member as the next member’s initial guess.
- Converting only representative or milestone family members by default.
- Changing CR3BP orbit generation scripts.
- Changing plotting scripts or downstream visualization behavior.
- Changing e2m2e solver internals.
- Adding a GUI for the redesigned conversion workflows.
- Adding database storage or non-JSON output formats.
- Adding automatic SPICE kernel download or installation.
- Supporting non-Earth-Moon CR3BP systems unless already supported by existing inputs and constants.
- Requiring real SPICE kernels for the primary unit test suite.

## Further Notes

- The current single DRO and single Halo scripts already share a nearly identical five-step pipeline: load orbit, sample patch points, convert synodic states to J2000, run multiple shooting correction, validate and save.
- The current DRO script has a hardcoded input path and default `standard` method; the redesign replaces this with explicit CLI input and default `two_level`.
- The current Halo script can implicitly choose the latest Halo output through environment/default behavior; the redesign removes implicit latest-file selection.
- Existing family JSON files use a top-level `orbits` list, while single-orbit JSON files use top-level orbit fields.
- The shared conversion module is the main deep module opportunity: it should encapsulate the expensive and error-prone workflow behind a small interface that is straightforward to mock and test.
- The domain glossary records that **轨道族转换** means full-family, per-orbit independent conversion with default continue-on-failure behavior.
