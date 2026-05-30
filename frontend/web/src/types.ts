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
  ports_by_type: Partial<Record<ConnectorType, PortConnector[]>>;
  note: string;
};

export type CabinetLayoutItem = {
  cabinet_uid: string;
  data_hall_id: string;
  cabinet_id: string;
  category: string;
  cabinet_group: string;
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

export type CabinetConnection = {
  target_cabinet_uid: string;
  target_category: string;
  target_cabinet_group: string;
  total_cables: number;
  cable_type_counts: Record<string, number>;
};

export type CabinetDetailResponse = {
  cabinet: CabinetLayoutItem;
  stats: CabinetStats;
  devices: Device[];
  connections: CabinetConnection[];
};
