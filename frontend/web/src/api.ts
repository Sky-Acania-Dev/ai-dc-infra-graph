import type {
  CableDetailResponse,
  CabinetDetailResponse,
  CabinetLayoutItem,
  AuthUser,
  CabinetCableDetail,
  Device,
  DeviceConnectionResponse,
  TopologyEnums,
  ValidationResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`);
  if (!response.ok) {
    throw new Error(`Failed to load current user: ${response.status}`);
  }
  return response.json();
}

export async function fetchTopologyEnums(): Promise<TopologyEnums> {
  const response = await fetch(`${API_BASE_URL}/topology/enums`);
  if (!response.ok) {
    throw new Error(`Failed to load topology enums: ${response.status}`);
  }
  return response.json();
}

export async function fetchCabinetLayout(dataHall: string): Promise<CabinetLayoutItem[]> {
  const response = await fetch(`${API_BASE_URL}/topology/layout/cabinets?data_hall=${encodeURIComponent(dataHall)}`);
  if (!response.ok) {
    throw new Error(`Failed to load cabinet layout: ${response.status}`);
  }
  return response.json();
}

export async function fetchCabinetDetail(cabinetUid: string): Promise<CabinetDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/cabinets/${encodeURIComponent(cabinetUid)}`);
  if (!response.ok) {
    throw new Error(`Failed to load cabinet detail: ${response.status}`);
  }
  return response.json();
}

export async function fetchCabinetConnectionCables(
  sourceCabinetUid: string,
  targetCabinetUid: string,
): Promise<CableDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/topology/cabinets/${encodeURIComponent(sourceCabinetUid)}/connections/${encodeURIComponent(targetCabinetUid)}/cables`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load cabinet cable details: ${response.status}`);
  }
  return response.json();
}

export async function fetchDeviceConnectionCables(
  sourceDeviceUid: string,
  targetDeviceUid: string,
): Promise<CableDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/topology/devices/${encodeURIComponent(sourceDeviceUid)}/connections/${encodeURIComponent(targetDeviceUid)}/cables`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load device cable details: ${response.status}`);
  }
  return response.json();
}

export async function fetchDeviceConnections(cabinetUid: string, rackUnit: number): Promise<DeviceConnectionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/topology/cabinets/${encodeURIComponent(cabinetUid)}/devices/${rackUnit}/connections`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load device connections: ${response.status}`);
  }
  return response.json();
}

export async function fetchValidationReport(): Promise<ValidationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/validation`);
  if (!response.ok) {
    throw new Error(`Failed to load validation report: ${response.status}`);
  }
  return response.json();
}

export async function updateCabinetStatus(cabinetUid: string, lifecycleStatus: string): Promise<CabinetLayoutItem> {
  const response = await fetch(`${API_BASE_URL}/topology/cabinets/${encodeURIComponent(cabinetUid)}/status`, {
    body: JSON.stringify({ lifecycle_status: lifecycleStatus }),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(`Failed to update cabinet status: ${response.status}`);
  }
  return response.json();
}

export async function updateDeviceStatus(deviceUid: string, lifecycleStatus: string): Promise<Device> {
  const response = await fetch(`${API_BASE_URL}/topology/devices/${encodeURIComponent(deviceUid)}/status`, {
    body: JSON.stringify({ lifecycle_status: lifecycleStatus }),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(`Failed to update device status: ${response.status}`);
  }
  return response.json();
}

export type UpdateCablePayload = {
  status?: string;
  progress?: Record<string, string>;
  current_phase?: {
    name: string;
    phase_type: string;
    value?: number | string | null;
    tasks?: Record<string, number>;
    enum_values?: string[];
  };
  length_used_meters?: number;
  length_meters?: number | null;
  note?: string;
};

export async function updateCable(cableUid: string, payload: UpdateCablePayload): Promise<CabinetCableDetail> {
  const response = await fetch(`${API_BASE_URL}/topology/cables/${encodeURIComponent(cableUid)}`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(`Failed to update cable: ${response.status}`);
  }
  return response.json();
}
