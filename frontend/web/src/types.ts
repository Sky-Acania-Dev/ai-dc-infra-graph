export type ConnectorType = "CAT6" | "LC" | "SC" | "MPO" | "power" | "other";

export type PortConnector = {
  uid: string;
  type: ConnectorType;
  note: string;
};

export type Device = {
  cabinet_id: string;
  rack_unit: number;
  device_model: string;
  lifecycle_status: string;
  aliases: string[];
  model_aliases: string[];
  ports_by_type: Partial<Record<ConnectorType, PortConnector[]>>;
  note: string;
};

export type CabinetLayoutItem = {
  cabinet_uid: string;
  data_hall_id: string;
  cabinet_id: string;
  category: string;
  cabinet_group: string;
  lifecycle_status: string;
  max_rack_unit: number;
  source_row: number | null;
  source_col: number | null;
};

export type CabinetStats = {
  devices: number;
  ports: number;
  cables: number;
  connected_cabinets: number;
  cable_type_counts: Record<string, number>;
};

export type CableStatusSummary = {
  completed: number;
  total: number;
  status_counts: Record<string, number>;
};

export type CabinetConnection = {
  target_cabinet_uid: string;
  target_category: string;
  target_cabinet_group: string;
  total_cables: number;
  cable_type_counts: Record<string, number>;
  status_summary: CableStatusSummary;
};

export type CabinetDetailResponse = {
  cabinet: CabinetLayoutItem;
  stats: CabinetStats;
  devices: Device[];
  intra_cabinet_connection: CabinetConnection | null;
  connections: CabinetConnection[];
};

export type CabinetCableDetail = {
  uid: string;
  group: string;
  status: string;
  cable_type: string;
  progress: Record<string, string>;
  length_meters: number | null;
  note: string;
  a_port_uid: string;
  z_port_uid: string;
  a_optic: string;
  z_optic: string;
};

export type CabinetCableDetailResponse = {
  source_cabinet_uid: string;
  target_cabinet_uid: string;
  cables: CabinetCableDetail[];
};

export type DeviceCableDetailResponse = {
  source_device_uid: string;
  target_device_uid: string;
  cables: CabinetCableDetail[];
};

export type CableDetailResponse = CabinetCableDetailResponse | DeviceCableDetailResponse;

export type DeviceConnection = {
  target_device_uid: string;
  target_cabinet_uid: string;
  target_rack_unit: number;
  total_cables: number;
  cable_type_counts: Record<string, number>;
  status_summary: CableStatusSummary;
};

export type DeviceConnectionResponse = {
  source_device_uid: string;
  source_cabinet_uid: string;
  source_rack_unit: number;
  connected_cabinet_uids: string[];
  connected_devices: DeviceConnection[];
};

export type PortConnectionFinding = {
  port_uid: string;
  count: number;
  message: string;
  examples: ValidationCableRowExample[];
};

export type ValidationCableRowExample = {
  status: string;
  group: string;
  cable_type: string;
  a_port_uid: string;
  z_port_uid: string;
  a_device_model: string;
  z_device_model: string;
};

export type DeviceModelRowExample = {
  side: string;
  status: string;
  group: string;
  port_uid: string;
  cable_type: string;
  device_name: string;
  device_model: string;
};

export type DeviceModelFinding = {
  device_uid: string;
  classification: string;
  models: ModelCount[];
  normalized_models: ModelCount[];
  examples: DeviceModelRowExample[];
};

export type ModelCount = {
  value: string;
  count: number;
};

export type ValidationResponse = {
  summary: {
    port_collision_findings: number;
    device_model_mismatches: number;
    device_model_format_issues: number;
  };
  port_collision_findings: PortConnectionFinding[];
  device_model_mismatches: DeviceModelFinding[];
  device_model_format_issues: DeviceModelFinding[];
};
