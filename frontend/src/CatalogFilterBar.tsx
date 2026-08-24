// 轨道库过滤栏

import { useEffect, useState } from "react";
import { Form, Select, InputNumber, Button, Space, message, Modal, Input } from "antd";
import { SearchOutlined, DownloadOutlined, RedoOutlined } from "@ant-design/icons";
import { catalogQuery, catalogExport } from "./catalogApi";
import type { ArtifactSummary } from "./projectApi";

export interface CatalogFilterBarProps {
  onResults: (artifacts: ArtifactSummary[], count: number, message: string) => void;
  onSelectRecord?: (record: any) => void;
}

export function CatalogFilterBar({ onResults }: CatalogFilterBarProps) {
  const [family, setFamily] = useState<string | undefined>(undefined);
  const [libration, setLibration] = useState<number | undefined>(undefined);
  const [jacobiMin, setJacobiMin] = useState<number | undefined>(undefined);
  const [jacobiMax, setJacobiMax] = useState<number | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportDest, setExportDest] = useState("./export_package.zip");
  const [exporting, setExporting] = useState(false);

  const executeQuery = async () => {
    setBusy(true);
    try {
      const filters: Record<string, unknown> = {};
      if (family) filters.orbit_family = family;
      if (libration) filters.libration_point = libration;
      if (jacobiMin !== undefined) filters.jacobi_min = jacobiMin;
      if (jacobiMax !== undefined) filters.jacobi_max = jacobiMax;

      const resp = await catalogQuery(filters);
      const records = resp.records || [];
      onResults(
        records.map((r) => ({
          artifactId: String(r.record_id ?? ""),
          artifactType: r.source_tool === "orbit_family_generation" || (r.member_count ?? 0) > 1 ? "family" : "orbit",
          label: `${String(r.orbit_family ?? "")} (${r.member_count ?? 1} 成员)`,
          orbitType: String(r.orbit_family ?? ""),
          sourceTool: String(r.source_tool ?? ""),
          recordId: (r.record_id as string) ?? null,
          createdAt: String(r.created_at ?? ""),
          hasEphemeris: Boolean(r.has_ephemeris),
        })),
        records.length,
        resp.message || `查询到 ${records.length} 条记录`,
      );
    } catch (e) {
      message.error(`查询失败: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    executeQuery();
  }, []);

  const handleExportPackage = async () => {
    setExporting(true);
    try {
      const filters: Record<string, unknown> = {};
      if (family) filters.orbit_family = family;
      if (libration) filters.libration_point = libration;
      if (jacobiMin !== undefined) filters.jacobi_min = jacobiMin;
      if (jacobiMax !== undefined) filters.jacobi_max = jacobiMax;

      const count = await catalogExport(filters, exportDest);
      message.success(`成功导出 ${count} 条轨道记录到 ${exportDest}`);
      setExportModalOpen(false);
    } catch (e) {
      message.error(`导出失败: ${String(e)}`);
    } finally {
      setExporting(false);
    }
  };

  const handleReset = () => {
    setFamily(undefined);
    setLibration(undefined);
    setJacobiMin(undefined);
    setJacobiMax(undefined);
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <Form layout="vertical" size="small">
        <Form.Item label="轨道族类型" style={{ marginBottom: 6 }}>
          <Select
            allowClear
            placeholder="不限族"
            value={family}
            onChange={setFamily}
            options={[
              { label: "Halo", value: "HALO" },
              { label: "NRHO", value: "NRHO" },
              { label: "Axial", value: "AXIAL" },
              { label: "Lissajous", value: "LISSAJOUS" },
              { label: "DRO", value: "DRO" },
              { label: "DPO", value: "DPO" },
              { label: "SPO", value: "SPO" },
              { label: "LPO", value: "LPO" },
              { label: "Horseshoe", value: "HORSESHOE" },
            ]}
          />
        </Form.Item>

        <Form.Item label="平动点" style={{ marginBottom: 6 }}>
          <Select
            allowClear
            placeholder="不限平动点"
            value={libration}
            onChange={setLibration}
            options={[
              { label: "L1", value: 1 },
              { label: "L2", value: 2 },
              { label: "L3", value: 3 },
              { label: "L4", value: 4 },
              { label: "L5", value: 5 },
            ]}
          />
        </Form.Item>

        <Space orientation="horizontal" style={{ width: "100%", marginBottom: 8 }} size={6}>
          <Form.Item label="Jacobi 下限" style={{ marginBottom: 0, flex: 1 }}>
            <InputNumber
              style={{ width: "100%" }}
              step={0.05}
              placeholder="Min"
              value={jacobiMin}
              onChange={(v) => setJacobiMin(v ?? undefined)}
            />
          </Form.Item>
          <Form.Item label="Jacobi 上限" style={{ marginBottom: 0, flex: 1 }}>
            <InputNumber
              style={{ width: "100%" }}
              step={0.05}
              placeholder="Max"
              value={jacobiMax}
              onChange={(v) => setJacobiMax(v ?? undefined)}
            />
          </Form.Item>
        </Space>

        <Space orientation="horizontal" style={{ width: "100%" }} size={6}>
          <Button
            type="primary"
            icon={<SearchOutlined />}
            loading={busy}
            onClick={executeQuery}
            style={{ flex: 1 }}
          >
            查询
          </Button>
          <Button icon={<RedoOutlined />} onClick={handleReset} title="重置过滤条件" />
          <Button
            icon={<DownloadOutlined />}
            onClick={() => setExportModalOpen(true)}
            title="导出教学案例包"
          >
            导出包
          </Button>
        </Space>
      </Form>

      <Modal
        title="导出教学案例包 (Catalog Export)"
        open={exportModalOpen}
        onCancel={() => setExportModalOpen(false)}
        onOk={handleExportPackage}
        confirmLoading={exporting}
        okText="开始打包导出"
        cancelText="取消"
        width={450}
      >
        <div style={{ marginBottom: 8 }}>
          将根据当前过滤条件将匹配的轨道记录打包并导出到指定路径。
        </div>
        <Form layout="vertical" size="small">
          <Form.Item label="目标保存路径 (zip 或目录)">
            <Input
              value={exportDest}
              onChange={(e) => setExportDest(e.target.value)}
              placeholder="./catalog_export.zip"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
