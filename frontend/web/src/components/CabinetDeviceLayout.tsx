import type { Device } from "../types";

type CabinetDeviceLayoutProps = {
  devices: Device[];
};

export function CabinetDeviceLayout({ devices }: CabinetDeviceLayoutProps) {
  const devicesByRu = new Map<number, Device[]>();
  for (const device of devices) {
    devicesByRu.set(device.rack_unit, [...(devicesByRu.get(device.rack_unit) ?? []), device]);
  }

  return (
    <section className="device-layout">
      <div className="section-title">Rack Units</div>
      <div className="rack-grid">
        {Array.from({ length: 42 }, (_, index) => 42 - index).map((rackUnit) => {
          const unitDevices = devicesByRu.get(rackUnit) ?? [];
          return (
            <div className={`rack-row ${unitDevices.length ? "has-device" : ""}`} key={rackUnit}>
              <span className="rack-unit">U{rackUnit}</span>
              <div className="rack-device">
                {unitDevices.map((device, index) => (
                  <div className="device-chip" key={`${device.rack_unit}-${device.device_model}-${index}`} title={device.note}>
                    <span>{device.device_model}</span>
                    <small>{portCount(device)} ports</small>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function portCount(device: Device): number {
  return Object.values(device.ports_by_type).reduce((total, ports) => total + (ports?.length ?? 0), 0);
}
