import { describe, it, expect } from "vitest";
import {
  UNIT_DEFINITIONS,
  convertValue,
  getBranchDefaults,
  ENUM_OPTIONS,
  formatRangePrompt,
  getFieldApplicability,
  TU_SECONDS,
} from "./index";

describe("参数覆写层 (paramOverlay)", () => {
  it("17 个单位字段正确注册且首项为标准单位 (toStandard = 1.0)", () => {
    const fields = Object.keys(UNIT_DEFINITIONS);
    expect(fields.length).toBeGreaterThanOrEqual(17);
    for (const field of fields) {
      const units = UNIT_DEFINITIONS[field];
      expect(units.length).toBeGreaterThanOrEqual(2);
      expect(units[0].toStandard).toBe(1.0);
    }
  });

  it("单位换算正确：km <-> m <-> DU", () => {
    // amplitude: km 为标准单位
    // amplitude: km is the standard unit.
    expect(convertValue("amplitude", 384400, "km", "DU")).toBeCloseTo(1.0, 6);
    expect(convertValue("amplitude", 1.0, "DU", "km")).toBeCloseTo(384400, 4);
    expect(convertValue("amplitude", 50, "km", "m")).toBe(50000);
    expect(convertValue("amplitude", 50000, "m", "km")).toBe(50);
  });

  it("时间单位换算正确：年 <-> 月 <-> 日 <-> 秒 <-> TU", () => {
    // duration: 年 为 GUI 标准单位 (facade 会换算为秒)
    // duration: years is the GUI standard unit (the facade converts to seconds).
    expect(convertValue("duration", 1.0, "年", "月")).toBeCloseTo(12.0, 4);
    expect(convertValue("duration", 1.0, "月", "年")).toBeCloseTo(1 / 12, 6);
    expect(convertValue("duration", 365.25, "日", "年")).toBeCloseTo(1.0, 4);
  });

  it("TU 换算锚定 TU_SECONDS 常量（#438）：output_step 1 TU = TU_SECONDS 秒", () => {
    // TU 秒值收敛为单一常量 TU_SECONDS（对齐 commons.units.TU_SECONDS）；
    // output_step 标准单位为秒，1 TU 应换算为该常量秒数。
    // The TU-in-seconds value lives in the single constant TU_SECONDS (aligned with
    // commons.units.TU_SECONDS); output_step's standard unit is seconds, so 1 TU must
    // convert to exactly that many seconds.
    expect(convertValue("output_step", 1.0, "TU", "秒")).toBeCloseTo(TU_SECONDS, 6);
    expect(convertValue("output_step", TU_SECONDS, "秒", "TU")).toBeCloseTo(1.0, 6);
    // control_interval 标准单位为天，1 TU = TU_SECONDS / 86400 天
    // control_interval's standard unit is days: 1 TU = TU_SECONDS / 86400 days.
    expect(convertValue("control_interval", 1.0, "TU", "天")).toBeCloseTo(TU_SECONDS / 86400, 8);
  });

  it("相位单位换算正确：周期份额 <-> 度 <-> 弧度", () => {
    // phase: 周期份额 (1.0)
    // phase: fraction of the period (1.0).
    expect(convertValue("phase", 0.5, "周期份额", "度")).toBeCloseTo(180, 4);
    expect(convertValue("phase", 180, "度", "周期份额")).toBeCloseTo(0.5, 4);
    expect(convertValue("phase", Math.PI, "弧度", "周期份额")).toBeCloseTo(0.5, 4);
  });

  it("15 种 design_orbit 轨道类型分支默认值齐备", () => {
    const expectedTypes = [
      "HALO", "DRO", "DPO", "NRHO", "LISSAJOUS", "AXIAL",
      "L4", "L5", "L4_SPO", "L5_SPO", "L4_LPO", "L5_LPO",
      "L4_HORSESHOE", "L5_HORSESHOE", "ELFO"
    ];
    for (const t of expectedTypes) {
      const defs = getBranchDefaults("design_orbit", t);
      expect(defs).toBeDefined();
      expect(typeof defs).toBe("object");
    }
    // 特征值检查
    // Eigenvalue checks.
    expect(getBranchDefaults("design_orbit", "DRO").amplitude).toBe(60000);
    expect(getBranchDefaults("design_orbit", "HALO").amplitude).toBe(30000);
    expect(getBranchDefaults("design_orbit", "NRHO").perilune_height).toBe(5000);
    expect(getBranchDefaults("design_orbit", "ELFO").semi_major_axis).toBe(6500);
  });

  it("整数枚举映射正确 (collinear_point, north_south, control_mode 等)", () => {
    expect(ENUM_OPTIONS["collinear_point"]).toBeDefined();
    expect(ENUM_OPTIONS["collinear_point"].find((o) => o.value === 2)?.label).toContain("L2");

    expect(ENUM_OPTIONS["north_south"]).toBeDefined();
    expect(ENUM_OPTIONS["north_south"].find((o) => o.value === 1)?.label).toContain("北族");
    expect(ENUM_OPTIONS["north_south"].find((o) => o.value === 2)?.label).toContain("南族");

    expect(ENUM_OPTIONS["control_mode"].length).toBe(6);
  });

  it("范围提示文案格式化正确", () => {
    expect(formatRangePrompt(0, 100, "km")).toBe("可填范围: 0 ~ 100 km");
    expect(formatRangePrompt(0, undefined, "km")).toBe("可填范围: ≥ 0 km");
    expect(formatRangePrompt(undefined, 100, "km")).toBe("可填范围: ≤ 100 km");
    expect(formatRangePrompt(undefined, undefined, "km")).toBe("无范围约束");
  });

  it("design_orbit 字段适用性过滤正确暴露各族核心字段", () => {
    const haloFields = getFieldApplicability("design_orbit", "HALO");
    expect(haloFields).toContain("orbit_type");
    expect(haloFields).toContain("amplitude");
    expect(haloFields).toContain("phase");
    expect(haloFields).toContain("collinear_point");
    expect(haloFields).toContain("north_south");
    expect(haloFields).toContain("epoch");
    expect(haloFields).toContain("duration");
    expect(haloFields).toContain("output_step");
    expect(haloFields).toContain("correction_method");

    const nrhoFields = getFieldApplicability("design_orbit", "NRHO");
    expect(nrhoFields).toContain("perilune_height");
    expect(nrhoFields).toContain("north_south");

    const elfoFields = getFieldApplicability("design_orbit", "ELFO");
    expect(elfoFields).toContain("semi_major_axis");
    expect(elfoFields).toContain("inclination");
    expect(elfoFields).toContain("arg_of_pericenter");
  });
});
describe("转移设计类型联动 (transfer_design)", () => {
  it("四种 transfer_type 的适用字段：HMN 显目标半径，LGA/WSB 显搜索参数且都不显 target_ephemeris（由 GUI 注入）", () => {
    const hmn = getFieldApplicability("transfer_design", "HMN");
    expect(hmn).toContain("target_orbit_radius_km");
    expect(hmn).not.toContain("lga_search_params");

    const lga = getFieldApplicability("transfer_design", "LGA");
    expect(lga).toContain("lga_search_params");
    expect(lga).not.toContain("target_orbit_radius_km");
    expect(lga).not.toContain("target_ephemeris");

    const wsb = getFieldApplicability("transfer_design", "WSB");
    expect(wsb).toContain("wsb_search_params");
    expect(wsb).not.toContain("target_ephemeris");

    for (const fields of [hmn, lga, wsb]) {
      for (const common of ["transfer_type", "tli_epoch", "parking_alt_km", "incl_deg", "flight_path_deg", "tof_range"]) {
        expect(fields).toContain(common);
      }
    }
  });

  it("HMN 分支默认值：transfer_type 自身 + 地心目标半径取地月平均距离", () => {
    expect(getBranchDefaults("transfer_design", "HMN")).toEqual({
      transfer_type: "HMN",
      target_orbit_radius_km: 384400,
    });
  });

  it("ENUM_OPTIONS.transfer_type 提供四项中文标签", () => {
    expect(ENUM_OPTIONS.transfer_type.map((o) => o.value)).toEqual(["HMN", "LGA", "WSB", "low_thrust"]);
  });
});
