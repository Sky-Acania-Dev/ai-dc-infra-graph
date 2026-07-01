import type {
  CableDetailResponse,
  CabinetDetailResponse,
  CabinetLayoutItem,
  AuthUser,
  BulkOperationResponse,
  CabinetCableDetail,
  ChangeOrderRecord,
  DataHallCableSummaryResponse,
  Device,
  DeviceConnectionResponse,
  EntityGroupRecord,
  OperationListResponse,
  OperationResponse,
  TopologyEnums,
  ValidationResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://100.121.214.15:8000";

export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/me`);
  if (!response.ok) {
    throw new Error(`Failed to load current user: ${response.status}`);
  }
  return response.json();
}


export type SaveEntityGroupPayload = {
  name: string;
  description?: string;
  entity_type?: string;
  member_uids?: string[];
  metadata_json?: Record<string, unknown>;
};

export type UpdateEntityGroupPayload = Partial<Omit<SaveEntityGroupPayload, "entity_type">>;

export async function fetchEntityGroups(entityType = "cable"): Promise<EntityGroupRecord[]> {
  const params = new URLSearchParams({ entity_type: entityType });
  const response = await fetch(`${API_BASE_URL}/entity-groups?${params.toString()}`);
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load entity groups"));
  }
  return response.json();
}

export async function createEntityGroup(payload: SaveEntityGroupPayload): Promise<EntityGroupRecord> {
  const response = await fetch(`${API_BASE_URL}/entity-groups`, {
    body: JSON.stringify({ ...payload, entity_type: payload.entity_type ?? "cable" }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to create entity group"));
  }
  return response.json();
}

export async function updateEntityGroup(groupUid: string, payload: UpdateEntityGroupPayload): Promise<EntityGroupRecord> {
  const response = await fetch(`${API_BASE_URL}/entity-groups/${encodeURIComponent(groupUid)}`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update entity group"));
  }
  return response.json();
}

export async function fetchEntityGroupCables(groupUid: string): Promise<CableDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/entity-groups/${encodeURIComponent(groupUid)}/cables`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load group cable details"));
  }
  return response.json();
}

export async function addEntityGroupMembers(groupUid: string, memberUids: string[]): Promise<EntityGroupRecord> {
  const response = await fetch(`${API_BASE_URL}/entity-groups/${encodeURIComponent(groupUid)}/members`, {
    body: JSON.stringify({ member_uids: memberUids }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to add group members"));
  }
  return response.json();
}

export async function deleteEntityGroup(groupUid: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/entity-groups/${encodeURIComponent(groupUid)}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to delete entity group"));
  }
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

export async function fetchDataHallCableSummary(dataHall: string): Promise<DataHallCableSummaryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/topology/data-halls/${encodeURIComponent(dataHall)}/cables/summary`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load data hall cable summary: ${response.status}`);
  }
  return response.json();
}

export async function fetchDataHallCables(
  dataHall: string,
  scope: "internal" | "external",
  cableType: string,
  targetDataHall?: string | null,
  limit = 500,
  offset = 0,
): Promise<CableDetailResponse> {
  const params = new URLSearchParams({ scope, cable_type: cableType });
  if (targetDataHall) params.set("target_data_hall", targetDataHall);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const response = await fetch(
    `${API_BASE_URL}/topology/data-halls/${encodeURIComponent(dataHall)}/cables?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load data hall cable details: ${response.status}`);
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

export async function fetchCabinetChangeOrderCables(
  cabinetUid: string,
  changeStatus: "red" | "yellow" | "cyan" | "replaced",
  changeOrderKeys: string[] = [],
): Promise<CableDetailResponse> {
  const params = new URLSearchParams({ change_status: changeStatus });
  for (const key of changeOrderKeys) params.append("change_order_key", key);
  const response = await fetch(
    `${API_BASE_URL}/topology/cabinets/${encodeURIComponent(cabinetUid)}/change-order-cables?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load cabinet change order cable details: ${response.status}`);
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

export async function fetchChangeOrders(): Promise<ChangeOrderRecord[]> {
  const response = await fetch(`${API_BASE_URL}/change-orders`);
  if (!response.ok) {
    throw new Error(`Failed to load change orders: ${response.status}`);
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

export async function revalidateTopology(): Promise<ValidationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/validation/revalidate`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to revalidate topology"));
  }
  return response.json();
}

export async function updateCabinetStatus(
  cabinetUid: string,
  lifecycleStatus: string,
  expectedVersion?: number | null,
): Promise<OperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/cabinets/${encodeURIComponent(cabinetUid)}/status`, {
    body: JSON.stringify({ lifecycle_status: lifecycleStatus, expected_version: expectedVersion ?? undefined }),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update cabinet status"));
  }
  return operationResponseFromJson(await response.json(), "update cabinet status");
}

export async function updateDeviceStatus(
  deviceUid: string,
  lifecycleStatus: string,
  expectedVersion?: number | null,
): Promise<OperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/devices/${encodeURIComponent(deviceUid)}/status`, {
    body: JSON.stringify({ lifecycle_status: lifecycleStatus, expected_version: expectedVersion ?? undefined }),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update device status"));
  }
  return operationResponseFromJson(await response.json(), "update device status");
}

export async function bulkUpdateLifecycleStatus(
  entityType: "cabinet" | "device",
  entityUids: string[],
  lifecycleStatus: string,
  expectedVersion?: number | null,
): Promise<BulkOperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/bulk/status`, {
    body: JSON.stringify({
      entity_type: entityType,
      entity_uids: entityUids,
      lifecycle_status: lifecycleStatus,
      expected_version: expectedVersion ?? undefined,
      source_type: "manual_bulk",
    }),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Failed to bulk update ${entityType} status`));
  }
  return bulkOperationResponseFromJson(await response.json(), `bulk update ${entityType} status`);
}

export type UpdateCablePayload = {
  status?: string;
  progress?: Record<string, string>;
  current_phase?: {
    name: string;
    value?: number | string | null;
    tasks?: Record<string, number>;
    task_values?: Record<string, { task_type: string; value: number | string | null; enum_values?: string[] }>;
  };
  length_used_meters?: number | null;
  length_meters?: number | null;
  note?: string | null;
  expected_version?: number | null;
};

export async function updateCable(cableUid: string, payload: UpdateCablePayload): Promise<OperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/cables/${encodeURIComponent(cableUid)}`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update cable"));
  }
  return operationResponseFromJson(await response.json(), "update cable");
}

export async function undoOperation(): Promise<OperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/operations/undo`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to undo operation: ${response.status}`);
  }
  return operationResponseFromJson(await response.json(), "undo operation");
}

export async function redoOperation(): Promise<OperationResponse> {
  const response = await fetch(`${API_BASE_URL}/topology/operations/redo`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to redo operation: ${response.status}`);
  }
  return operationResponseFromJson(await response.json(), "redo operation");
}

export type FetchOperationsParams = {
  limit?: number;
  after?: number | null;
  offset?: number;
  operationType?: string;
  userUid?: string;
  changeOrderKey?: string;
  startTime?: string | null;
  endTime?: string | null;
};

export async function fetchOperations(
  limitOrParams: number | FetchOperationsParams = 100,
  after?: number | null,
): Promise<OperationListResponse> {
  const options = typeof limitOrParams === "number" ? { limit: limitOrParams, after } : limitOrParams;
  const params = new URLSearchParams({ limit: String(options.limit ?? 100) });
  if (options.after != null) params.set("after", String(options.after));
  if (options.offset != null) params.set("offset", String(options.offset));
  if (options.operationType) params.set("operation_type", options.operationType);
  if (options.userUid) params.set("user_uid", options.userUid);
  if (options.changeOrderKey) params.set("change_order_key", options.changeOrderKey);
  if (options.startTime) params.set("start_time", options.startTime);
  if (options.endTime) params.set("end_time", options.endTime);
  const response = await fetch(`${API_BASE_URL}/topology/operations?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to load operations: ${response.status}. Restart the backend so /topology/operations is registered.`);
  }
  return response.json();
}

function operationResponseFromJson(payload: unknown, action: string): OperationResponse {
  if (
    payload &&
    typeof payload === "object" &&
    "operation" in payload &&
    "version" in payload &&
    (payload as OperationResponse).operation
  ) {
    return payload as OperationResponse;
  }
  throw new Error(
    `Failed to ${action}: backend returned the old response shape. Restart the backend so operation-log endpoints are active.`,
  );
}

function bulkOperationResponseFromJson(payload: unknown, action: string): BulkOperationResponse {
  if (
    payload &&
    typeof payload === "object" &&
    "operations" in payload &&
    Array.isArray((payload as BulkOperationResponse).operations) &&
    "version" in payload
  ) {
    return payload as BulkOperationResponse;
  }
  throw new Error(
    `Failed to ${action}: backend returned the old response shape. Restart the backend so bulk operation endpoints are active.`,
  );
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  let detail: unknown = null;
  try {
    detail = (await response.json()).detail;
  } catch {
    return `${fallback}: ${response.status}`;
  }
  if (typeof detail === "string") return `${fallback}: ${detail}`;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    return `${fallback}: ${detail.message}`;
  }
  return `${fallback}: ${response.status}`;
}

