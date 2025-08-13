import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Map,
  RefreshCw,
  Zap,
  Server,
  Wifi,
  Route,
  Play,
  Pause,
  Power,
  Settings,
  AlertTriangle,
  Check,
  Circle,
} from "lucide-react";

/**
 * ProtocolConfigSection (Redesigned from scratch)
 * -------------------------------------------------
 * Goals:
 * - Modern, clean, and highly scannable UI
 * - Clear primary/secondary actions with consistent variants
 * - Compact status badges with iconography
 * - Segmented control to switch active protocol quickly
 * - Sticky header inside the section for quick refresh + timestamp
 * - Skeletons for loading; graceful error state
 * - Accessibility-aware: focus states, aria-attrs, semantic elements
 *
 * External API kept compatible with the previous version.
 */

// ===================== Primitive UI =====================
const cx = (...parts) => parts.filter(Boolean).join(" ");

const Card = ({ children, className = "" }) => (
  <section
    className={cx(
      "rounded-2xl border border-gray-200 bg-white shadow-sm",
      "transition-all duration-200",
      className
    )}
  >
    {children}
  </section>
);

const CardHeader = ({ title, actions, subtitle }) => (
  <header className="flex items-start justify-between p-5">
    <div>
      <h4 className="text-gray-900 font-semibold tracking-tight">{title}</h4>
      {subtitle && (
        <p className="text-sm text-gray-500 mt-1 leading-relaxed">{subtitle}</p>
      )}
    </div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </header>
);

const CardBody = ({ children, className = "" }) => (
  <div className={cx("p-5 pt-0", className)}>{children}</div>
);

const Button = ({
  children,
  icon: Icon,
  variant = "primary",
  size = "md",
  className = "",
  disabled,
  onClick,
  type = "button",
  ariaLabel,
}) => {
  const variants = {
    primary:
      "bg-gray-900 text-white hover:bg-black focus:ring-2 focus:ring-gray-400",
    secondary:
      "bg-white text-gray-900 border border-gray-300 hover:bg-gray-50 focus:ring-2 focus:ring-gray-300",
    success:
      "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-300",
    danger:
      "bg-rose-600 text-white hover:bg-rose-700 focus:ring-2 focus:ring-rose-300",
    subtle:
      "bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-2 focus:ring-gray-300",
    ghost:
      "bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-2 focus:ring-gray-300",
  };
  const sizes = {
    sm: "h-8 px-3 text-xs rounded-lg",
    md: "h-10 px-4 text-sm rounded-lg",
    lg: "h-11 px-5 text-sm rounded-xl",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cx(
        "inline-flex items-center gap-2 justify-center font-medium",
        "transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
    >
      {Icon && <Icon size={16} aria-hidden="true" />} {children}
    </button>
  );
};

const Badge = ({ children, tone = "neutral", icon: Icon }) => {
  const tones = {
    neutral: "bg-gray-100 text-gray-800 border-gray-200",
    info: "bg-blue-100 text-blue-800 border-blue-200",
    success: "bg-emerald-100 text-emerald-800 border-emerald-200",
    warn: "bg-amber-100 text-amber-800 border-amber-200",
    danger: "bg-rose-100 text-rose-800 border-rose-200",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        tones[tone]
      )}
    >
      {Icon && <Icon size={12} aria-hidden="true" />} {children}
    </span>
  );
};

const Metric = ({ icon: Icon, label, value, tone = "neutral" }) => {
  const toneMap = {
    neutral: { wrap: "bg-gray-50 border-gray-200", icon: "text-gray-600" },
    blue: { wrap: "bg-blue-50 border-blue-200", icon: "text-blue-600" },
    green: { wrap: "bg-emerald-50 border-emerald-200", icon: "text-emerald-600" },
    amber: { wrap: "bg-amber-50 border-amber-200", icon: "text-amber-600" },
    purple: { wrap: "bg-violet-50 border-violet-200", icon: "text-violet-600" },
  };
  const t = toneMap[tone] || toneMap.neutral;
  return (
    <div className={cx("rounded-xl p-4 border", t.wrap)}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={18} className={t.icon} aria-hidden="true" />
        <span className="text-xs text-gray-600">{label}</span>
      </div>
      <div className="text-sm font-semibold text-gray-900">{value}</div>
    </div>
  );
};

const Segmented = ({ value, onChange, options }) => (
  <div
    role="tablist"
    aria-label="Active protocol"
    className="grid grid-cols-4 rounded-xl border border-gray-200 bg-gray-50 p-1"
  >
    {options.map((opt) => {
      const active = value === opt.value;
      return (
        <button
          key={opt.value}
          role="tab"
          aria-selected={active}
          onClick={() => onChange(opt.value)}
          className={cx(
            "relative h-9 rounded-lg text-sm font-medium",
            "transition-all outline-none focus-visible:ring-2 focus-visible:ring-gray-300",
            active
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-600 hover:text-gray-900"
          )}
        >
          <span className="inline-flex items-center gap-2 px-3">
            {opt.icon && <opt.icon size={16} aria-hidden="true" />}
            {opt.label}
          </span>
        </button>
      );
    })}
  </div>
);

const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="block text-sm font-medium text-gray-700 mb-2">{label}</span>
    {children}
    {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
  </label>
);

const Input = ({ className = "", ...props }) => (
  <input
    {...props}
    className={cx(
      "w-full h-10 rounded-lg border border-gray-300 bg-white",
      "px-3 text-sm text-gray-900 placeholder-gray-400",
      "focus:ring-2 focus:ring-gray-300 focus:border-gray-400",
      className
    )}
  />
);

const Select = ({ className = "", ...props }) => (
  <select
    {...props}
    className={cx(
      "w-full h-10 rounded-lg border border-gray-300 bg-white",
      "px-3 text-sm text-gray-900",
      "focus:ring-2 focus:ring-gray-300 focus:border-gray-400",
      className
    )}
  />
);

const Divider = () => <div className="h-px bg-gray-100" />;

// ===================== Main Component =====================
export function ProtocolConfigSection({
  local = { protocol: "static", interfaces: [] },
  sections = { protocol: true },
  dispatch = () => {},
  onToggle = () => {},
  selectedNode = { id: "r1" },
  apiCall,
  showMessage = (msg, type) => console.log(`${type.toUpperCase()}: ${msg}`),
  debug = false,
}) {
  const [protocolStatus, setProtocolStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const didSyncLocalProtocol = useRef(false);

  // API wrapper
  const api = async (path, options) => {
    if (debug) console.log(`API call: ${path}`, options || {});
    const res = await apiCall(path, options);
    if (debug) console.log(`API response:`, res);
    return res;
  };

  // Fetch protocol status with robust data extraction
  const fetchProtocolStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const path = `/protocol-management/devices/${selectedNode.id}/routing-protocols`;
      const response = await api(path);

      if (response?.success) {
        const data = response.data?.data || response.data; // normalize nested shape
        setProtocolStatus(data);
        setLastUpdated(new Date());
      } else {
        throw new Error(response?.message || "Failed to fetch protocol status");
      }
    } catch (err) {
      setError(err.message);
      showMessage(`Failed to fetch protocol status: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    didSyncLocalProtocol.current = false;
    fetchProtocolStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNode.id]);

  useEffect(() => {
    if (protocolStatus?.current_status?.primary_protocol && !didSyncLocalProtocol.current) {
      dispatch({
        type: "SET_FIELD",
        field: "protocol",
        value: protocolStatus.current_status.primary_protocol,
      });
      didSyncLocalProtocol.current = true;
    }
  }, [protocolStatus?.current_status?.primary_protocol, dispatch]);

  // View model for UI
  const vm = useMemo(() => {
    if (!protocolStatus) return null;

    const caps = protocolStatus.capabilities || {};
    const cur = protocolStatus.current_status || {};

    const createProtocolStatus = (protocol, daemon) => ({
      available: !!caps.daemons_available?.[daemon],
      running: !!cur.running_processes?.[daemon],
      port: cur.listening_ports?.[daemon] || null,
      active:
        cur.primary_protocol === protocol || (cur.active_protocols || []).includes(protocol),
    });

    return {
      primary: cur.primary_protocol || "static",
      activeList: cur.active_protocols || [],
      recommendation: caps.recommendation || "basic",
      frrAvailable: !!caps.fr_available,
      routes: cur.routing_table_size || 0,
      rip: createProtocolStatus("rip", "ripd"),
      ospf: createProtocolStatus("ospf", "ospfd"),
      bgp: createProtocolStatus("bgp", "bgpd"),
      zebra: {
        available: !!caps.daemons_available?.zebra,
        running: !!cur.running_processes?.zebra,
        port: cur.listening_ports?.zebra || null,
      },
    };
  }, [protocolStatus]);

  // Actions
  const startDaemon = async (protocol) => {
    try {
      const res = await api(
        `/protocol-management/devices/${selectedNode.id}/routing-protocols/${protocol}/start`,
        { method: "POST" }
      );
      if (!res?.success) throw new Error(res?.message || `Failed to start ${protocol}`);
      showMessage(`${protocol.toUpperCase()} started`, "success");
      await fetchProtocolStatus();
    } catch (err) {
      showMessage(err.message, "error");
    }
  };

  const stopDaemon = async (protocol) => {
    try {
      const res = await api(
        `/protocol-management/devices/${selectedNode.id}/routing-protocols/${protocol}/stop`,
        { method: "POST" }
      );
      if (!res?.success) throw new Error(res?.message || `Failed to stop ${protocol}`);
      showMessage(`${protocol.toUpperCase()} stopped`, "success");
      await fetchProtocolStatus();
    } catch (err) {
      showMessage(err.message, "error");
    }
  };

  const switchActiveProtocol = async (newProtocol) => {
    try {
      if (newProtocol === "static") {
        dispatch({ type: "SET_FIELD", field: "protocol", value: newProtocol });
        showMessage("Switched to static routing", "success");
        return;
      }

      // Ensure protocol daemon is running
      await startDaemon(newProtocol);

      // Set as primary
      await api(`/protocol-management/devices/${selectedNode.id}/routing-protocols/primary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ protocol: newProtocol }),
      });

      dispatch({ type: "SET_FIELD", field: "protocol", value: newProtocol });
      showMessage(`Switched to ${newProtocol.toUpperCase()}`, "success");
      await fetchProtocolStatus();
    } catch (err) {
      showMessage(`Failed to switch protocol: ${err.message}`, "error");
    }
  };

  // Derived lists
  const runningDaemons = Object.entries(
    protocolStatus?.current_status?.running_processes || {}
  )
    .filter(([, isRunning]) => isRunning)
    .map(([name]) => ({
      name,
      port: protocolStatus?.current_status?.listening_ports?.[name] || "N/A",
    }));

  const availableDaemons = Object.entries(
    protocolStatus?.capabilities?.daemons_available || {}
  )
    .filter(([, available]) => available)
    .map(([name]) => ({ name }));

  // ===================== UI States =====================
  if (loading) {
    return (
      <SectionShell
        title="Routing Protocol"
        icon={Map}
        expanded={sections.protocol}
        onToggle={() => onToggle("protocol")}
      >
        <div className="py-10 flex flex-col items-center gap-3">
          <RefreshCw className="animate-spin" />
          <p className="text-sm text-gray-600">Loading protocol status…</p>
          <div className="mt-4 grid w-full grid-cols-1 gap-4 md:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-20 rounded-xl bg-gray-100 animate-pulse border border-gray-200"
              />
            ))}
          </div>
        </div>
      </SectionShell>
    );
  }

  if (error) {
    return (
      <SectionShell
        title="Routing Protocol"
        icon={Map}
        expanded={sections.protocol}
        onToggle={() => onToggle("protocol")}
      >
        <div className="py-10 flex flex-col items-center text-center">
          <AlertTriangle className="text-rose-500" size={36} />
          <h4 className="mt-3 font-semibold text-gray-900">
            Failed to load protocol status
          </h4>
          <p className="mt-1 text-sm text-gray-600 max-w-md">{error}</p>
          <Button className="mt-4" icon={RefreshCw} onClick={fetchProtocolStatus}>
            Retry
          </Button>
        </div>
      </SectionShell>
    );
  }

  // ===================== Render =====================
  return (
    <SectionShell
      title="Routing Protocol"
      icon={Map}
      expanded={sections.protocol}
      onToggle={() => onToggle("protocol")}
    >
      {/* Sticky inner header */}
      <div className="sticky top-0 z-[1] -mx-6 border-b border-gray-100 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/60">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 text-sm text-gray-600">
              <Circle size={10} className="text-emerald-500" />
              Node <span className="font-medium text-gray-900">{selectedNode.id}</span>
            </span>
            <span className="text-gray-300">•</span>
            <span className="text-sm text-gray-500">
              {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Never updated"}
            </span>
          </div>
          <Button
            variant="secondary"
            icon={RefreshCw}
            onClick={fetchProtocolStatus}
            ariaLabel="Refresh status"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Overview metrics */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-4">
        <Metric icon={Server} label="Environment" value={vm?.recommendation || "basic"} tone="blue" />
        <Metric icon={Wifi} label="Primary Protocol" value={(vm?.primary || "static").toUpperCase()} tone="green" />
        <Metric
          icon={Route}
          label="FRR Status"
          value={vm?.frrAvailable ? "Available" : "Not Found"}
          tone={vm?.frrAvailable ? "green" : "amber"}
        />
        <Metric icon={Route} label="Routes" value={vm?.routes ?? 0} tone="purple" />
      </div>

      {/* Quick switch */}
      <Card className="mt-6">
        <CardHeader
          title="Active Protocol"
          subtitle="Choose which routing protocol should be primary on this node."
          actions={
            <Badge tone="info" icon={Zap}>
              Current: {(vm?.primary || "static").toUpperCase()}
            </Badge>
          }
        />
        <CardBody>
          <Segmented
            value={vm?.primary || "static"}
            onChange={switchActiveProtocol}
            options={[
              { label: "Static", value: "static", icon: Power },
              { label: "RIP", value: "rip", icon: Play },
              { label: "OSPF", value: "ospf", icon: Route },
              { label: "BGP", value: "bgp", icon: Settings },
            ]}
          />
        </CardBody>
      </Card>

      {/* Protocol controls */}
      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <ProtocolCard
          title="STATIC"
          status={{ available: true, running: vm?.primary === "static" }}
          isActive={vm?.primary === "static"}
          onStart={() => switchActiveProtocol("static")}
          onStop={() => {}}
          onMakeActive={() => switchActiveProtocol("static")}
          startDisabled={vm?.primary === "static"}
          stopDisabled={true}
          makeActiveDisabled={vm?.primary === "static"}
        />

        <ProtocolCard
          title="RIP"
          status={vm?.rip || {}}
          isActive={vm?.primary === "rip"}
          onStart={() => startDaemon("rip")}
          onStop={() => stopDaemon("rip")}
          onMakeActive={() => switchActiveProtocol("rip")}
          startDisabled={!vm?.rip?.available || vm?.rip?.running}
          stopDisabled={!vm?.rip?.running}
          makeActiveDisabled={!vm?.rip?.available || vm?.primary === "rip"}
        />

        <ProtocolCard
          title="OSPF"
          status={vm?.ospf || {}}
          isActive={vm?.primary === "ospf"}
          onStart={() => startDaemon("ospf")}
          onStop={() => stopDaemon("ospf")}
          onMakeActive={() => switchActiveProtocol("ospf")}
          startDisabled={!vm?.ospf?.available || vm?.ospf?.running}
          stopDisabled={!vm?.ospf?.running}
          makeActiveDisabled={!vm?.ospf?.available || vm?.primary === "ospf"}
        />

        <ProtocolCard
          title="BGP"
          status={vm?.bgp || {}}
          isActive={vm?.primary === "bgp"}
          onStart={() => startDaemon("bgp")}
          onStop={() => stopDaemon("bgp")}
          onMakeActive={() => switchActiveProtocol("bgp")}
          startDisabled={!vm?.bgp?.available || vm?.bgp?.running}
          stopDisabled={!vm?.bgp?.running}
          makeActiveDisabled={!vm?.bgp?.available || vm?.primary === "bgp"}
        />
      </div>

      {/* Daemon status */}
      <Card className="mt-6">
        <CardHeader title="Daemon Status" />
        <CardBody>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <DaemonList
              title="Running Processes"
              items={runningDaemons}
              emptyMessage="No active daemons"
              tone="success"
            />
            <DaemonList
              title="Available Daemons"
              items={availableDaemons}
              emptyMessage="No available daemons"
              tone="info"
            />
          </div>
        </CardBody>
      </Card>

      {/* Config forms */}
      {local.protocol === "bgp" && (
        <Card className="mt-6">
          <CardHeader title="BGP Configuration" />
          <CardBody>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <Field label="AS Number" hint="e.g., 65001">
                <Input
                  type="text"
                  value={local.bgpConfig?.as_number || ""}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_FIELD",
                      field: "bgpConfig",
                      value: { ...(local.bgpConfig || {}), as_number: e.target.value },
                    })
                  }
                  placeholder="65001"
                />
              </Field>
              <Field label="Router ID" hint="IPv4, e.g., 1.1.1.1">
                <Input
                  type="text"
                  value={local.bgpConfig?.router_id || ""}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_FIELD",
                      field: "bgpConfig",
                      value: { ...(local.bgpConfig || {}), router_id: e.target.value },
                    })
                  }
                  placeholder="1.1.1.1"
                />
              </Field>
            </div>
          </CardBody>
        </Card>
      )}

      {local.protocol === "ospf" && (
        <Card className="mt-6">
          <CardHeader title="OSPF Configuration" />
          <CardBody>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <Field label="Area ID" hint="Backbone is 0">
                <Input
                  type="text"
                  value={local.ospfConfig?.area_id || ""}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_FIELD",
                      field: "ospfConfig",
                      value: { ...(local.ospfConfig || {}), area_id: e.target.value },
                    })
                  }
                  placeholder="0"
                />
              </Field>
              <Field label="Router ID" hint="IPv4, e.g., 1.1.1.1">
                <Input
                  type="text"
                  value={local.ospfConfig?.router_id || ""}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_FIELD",
                      field: "ospfConfig",
                      value: { ...(local.ospfConfig || {}), router_id: e.target.value },
                    })
                  }
                  placeholder="1.1.1.1"
                />
              </Field>
            </div>
          </CardBody>
        </Card>
      )}

      {local.protocol === "rip" && (
        <Card className="mt-6">
          <CardHeader title="RIP Configuration" />
          <CardBody>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <Field label="RIP Version">
                <Select
                  value={local.ripConfig?.version || "2"}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_FIELD",
                      field: "ripConfig",
                      value: { ...(local.ripConfig || {}), version: e.target.value },
                    })
                  }
                >
                  <option value="1">Version 1</option>
                  <option value="2">Version 2</option>
                </Select>
              </Field>
            </div>
          </CardBody>
        </Card>
      )}
    </SectionShell>
  );
}

// ===================== Section Shell (Collapsible) =====================
const SectionShell = ({ title, icon: Icon, expanded, onToggle, children }) => (
  <section className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
    <button
      type="button"
      onClick={onToggle}
      className="w-full flex items-center justify-between px-6 py-4 bg-gray-50 hover:bg-gray-100 transition-colors"
      aria-expanded={expanded}
      aria-controls={`${title.replace(/\s+/g, "-").toLowerCase()}-content`}
    >
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-blue-50">
          <Icon className="text-blue-600" size={20} aria-hidden="true" />
        </div>
        <h3 className="font-semibold text-gray-900">{title}</h3>
      </div>
      <span className="text-gray-500 text-xl" aria-hidden="true">
        {expanded ? "−" : "+"}
      </span>
    </button>
    {expanded && (
      <div id={`${title.replace(/\s+/g, "-").toLowerCase()}-content`} className="px-6 pb-6">
        {children}
      </div>
    )}
  </section>
);

// ===================== Compound Pieces =====================
const ProtocolCard = ({
  title,
  status,
  isActive,
  onStart,
  onStop,
  onMakeActive,
  startDisabled,
  stopDisabled,
  makeActiveDisabled,
}) => (
  <Card>
    <CardHeader
      title={title}
      actions={
        <div className="flex items-center gap-2">
          <Badge tone={status?.available ? "success" : "danger"} icon={Check}>
            {status?.available ? "Available" : "Unavailable"}
          </Badge>
          <Badge tone={status?.running ? "info" : "neutral"} icon={status?.running ? Play : Pause}>
            {status?.running ? "Running" : "Stopped"}
          </Badge>
          {isActive && (
            <Badge tone="success" icon={Zap}>
              Active
            </Badge>
          )}
        </div>
      }
    />
    <Divider />
    <CardBody>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Button
          onClick={onStart}
          disabled={startDisabled}
          icon={Play}
          variant={status?.available && !status?.running ? "success" : "secondary"}
          className="w-full"
        >
          Start
        </Button>
        <Button
          onClick={onStop}
          disabled={stopDisabled}
          icon={Pause}
          variant={status?.running ? "danger" : "secondary"}
          className="w-full"
        >
          Stop
        </Button>
        <Button
          onClick={onMakeActive}
          disabled={makeActiveDisabled}
          icon={Settings}
          variant={!isActive ? "primary" : "secondary"}
          className="w-full"
        >
          {isActive ? "Active" : "Make Active"}
        </Button>
      </div>
      {typeof status?.port !== "undefined" && status?.port !== null && (
        <p className="mt-3 text-xs text-gray-500">Listening port: {status.port}</p>
      )}
    </CardBody>
  </Card>
);

const DaemonList = ({ title, items, emptyMessage, tone = "info" }) => {
  const toneMap = {
    info: {
      wrap: "border-blue-200 bg-blue-50",
      iconWrap: "bg-blue-100",
      icon: "text-blue-600",
    },
    success: {
      wrap: "border-emerald-200 bg-emerald-50",
      iconWrap: "bg-emerald-100",
      icon: "text-emerald-600",
    },
  }[tone];

  return (
    <div>
      <h4 className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-700">
        <Settings size={16} className={tone === "success" ? "text-emerald-600" : "text-blue-600"} />
        {title}
      </h4>
      <div className="space-y-3">
        {items.length > 0 ? (
          items.map((item) => (
            <div
              key={item.name}
              className={cx(
                "flex items-center rounded-xl border p-3",
                toneMap.wrap
              )}
            >
              <div className={cx("mr-3 rounded-lg p-2", toneMap.iconWrap)}>
                <Check size={16} className={toneMap.icon} />
              </div>
              <div className="min-w-0">
                <div className="truncate font-medium text-gray-900">{item.name}</div>
                {item.port && (
                  <div className="mt-1 text-xs text-gray-600">Port: {item.port}</div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 p-6 text-center text-gray-500">
            <Pause className="mx-auto text-gray-400" size={22} />
            <p className="mt-2 text-sm">{emptyMessage}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProtocolConfigSection;
