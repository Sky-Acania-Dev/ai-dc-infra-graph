export type ConnectorType = "CAT6" | "LC" | "SC" | "MPO" | "power" | "other";
export type UserRole = "manager" | "editor" | "viewer";

export type AuthUser = {
  uid: string;
  display_name: string;
  role: UserRole;
  is_dev_default: boolean;
};

export type TopologyEnums = {
  lifecycle_statuses: string[];
  construction_phases: string[];
  cable_import_statuses: string[];
  cable_progress_steps: string[];
  cable_progress_states: string[];
  cable_progress_phase_types: CableProgressPhaseType[];
  cable_progress_phase_names: string[];
  cable_progress_phases: CableProgressPhaseDefinition[];
};

export type CableProgressPhaseType = "single_percent" | "parallel_percent" | "enum_state";
export type CableProgressTaskType = "percent" | "enum";

export type CableProgressPhase = {
  name: string;
  phase_type: CableProgressPhaseType;
  value: number | string | null;
  tasks: Record<string, number>;
  enum_values: string[];
  task_values: Record<string, CableProgressTask>;
};

export type CableProgressPhaseDefinition = {
  name: string;
  tasks: CableProgressTaskDefinition[];
};

export type CableProgressTaskDefinition = {
  name: string;
  task_type: CableProgressTaskType;
  enum_values: string[];
  default_value: number | string | null;
};

export type CableProgressTask = {
  task_type: CableProgressTaskType;
  value: number | string | null;
  enum_values: string[];
};

export type PortConnector = {
  uid: string;
  type: ConnectorType;
  note: string;
};

export type Device = {
  cabinet_id: string;
  rack_unit: number;
  device_model: string;
  device_model_uid: string;
  rack_units: number;
  lifecycle_status: string;
  construction_phase: string;
  aliases: string[];
  model_aliases: string[];
  front_panel_svg: string;
  back_panel_svg: string;
  port_layout: DevicePortLayoutEntry[];
  port_layout_overrides: DevicePortLayoutEntry[];
  ports_by_type: Partial<Record<ConnectorType, PortConnector[]>>;
  change_operations: Operation[];
  note: string;
};

export type DevicePortLayoutEntry = {
  port_name: string;
  side: "front" | "back" | string;
  x: number;
  y: number;
  width: number;
  height: number;
  connector_type: ConnectorType;
  note: string;
};

export type DeviceModel = {
  uid: string;
  model_name: string;
  manufacturer: string;
  rack_units: number;
  device_instance_uids: string[];
  front_panel_svg: string;
  back_panel_svg: string;
  port_layout: DevicePortLayoutEntry[];
  note: string;
};

export type CabinetLayoutItem = {
  cabinet_uid: string;
  data_hall_id: string;
  cabinet_id: string;
  category: string;
  cabinet_group: string;
  lifecycle_status: string;
  construction_phase: string;
  max_rack_unit: number;
  cable_termination_percent: number;
  cable_dress_percent: number;
  source_row: number | null;
  source_col: number | null;
};

export type CabinetStats = {
  devices: number;
  ports: number;
  cables: number;
  connected_cabinets: number;
  cable_termination_percent: number;
  cable_dress_percent: number;
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

export type DataHallCableBucket = {
  scope: "internal" | "external";
  target_data_hall: string | null;
  total_cables: number;
  cable_type_counts: Record<string, number>;
  status_summary: CableStatusSummary;
};

export type DataHallCableSummaryResponse = {
  data_hall_id: string;
  internal: DataHallCableBucket;
  external: DataHallCableBucket[];
};

export type CabinetDetailResponse = {
  cabinet: CabinetLayoutItem;
  stats: CabinetStats;
  devices: Device[];
  intra_cabinet_connection: CabinetConnection | null;
  connections: CabinetConnection[];
  change_operations: Operation[];
};

export type CabinetCableDetail = {
  uid: string;
  group: string;
  status: string;
  cable_type: string;
  construction_phase: string;
  progress: Record<string, string>;
  current_phase: CableProgressPhase | null;
  designed_length_meters: number | null;
  length_used_meters: number;
  length_meters: number | null;
  note: string;
  a_port_uid: string;
  z_port_uid: string;
  a_optic: string;
  z_optic: string;
  change_status: "green" | "yellow" | "red";
};

export type CabinetCableDetailResponse = {
  source_cabinet_uid: string;
  target_cabinet_uid: string;
  cables: CabinetCableDetail[];
  total_cables?: number | null;
  limit?: number | null;
  offset?: number;
  has_more?: boolean;
};

export type DeviceCableDetailResponse = {
  source_device_uid: string;
  target_device_uid: string;
  cables: CabinetCableDetail[];
};

export type CableDetailResponse = CabinetCableDetailResponse | DeviceCableDetailResponse;

export type DeviceConnection = {
  target_device_uid: string;
  target_device_model: string;
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

export type Operation = {
  opId: number;
  type: string;
  entityType: "cabinet" | "device" | "cable" | string;
  entityId: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  timestamp: string;
  userUid?: string | null;
  userRole?: string | null;
  operationGroupUid?: string | null;
  sourceType?: string | null;
  sourceUid?: string | null;
  sourceOperator?: string | null;
};

export type OperationResponse = {
  ok: boolean;
  operation: Operation;
  version: number;
};

export type BulkOperationResponse = {
  ok: boolean;
  operations: Operation[];
  version: number;
};

export type OperationListResponse = {
  operations: Operation[];
  version: number;
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  operation_types: string[];
  user_uids: string[];
  min_timestamp?: string | null;
  max_timestamp?: string | null;
};
