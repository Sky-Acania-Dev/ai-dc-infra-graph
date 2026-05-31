import type { CabinetCableDetailResponse, CabinetDetailResponse, CabinetLayoutItem } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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
): Promise<CabinetCableDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/topology/cabinets/${encodeURIComponent(sourceCabinetUid)}/connections/${encodeURIComponent(targetCabinetUid)}/cables`,
  );
  if (!response.ok) {
    throw new Error(`Failed to load cabinet cable details: ${response.status}`);
  }
  return response.json();
}
