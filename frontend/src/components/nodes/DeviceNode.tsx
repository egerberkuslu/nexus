import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { DeviceType } from '@/types/topology'
import { 
  Monitor, 
  Network, 
  Router, 
  Wifi, 
  Smartphone, 
  Container as ContainerIcon, 
  Zap, 
  Server 
} from 'lucide-react'

const DeviceIcon = ({ type, className }: { type: DeviceType; className?: string }) => {
  const iconProps = { className: className || 'w-6 h-6', strokeWidth: 2 }
  
  switch (type) {
    case 'host':
      return <Monitor {...iconProps} />
    case 'switch':
      return <Network {...iconProps} />
    case 'router':
      return <Router {...iconProps} />
    case 'ap':
      return <Wifi {...iconProps} />
    case 'station':
      return <Smartphone {...iconProps} />
    case 'p4switch':
      return <Zap {...iconProps} />
    case 'controller':
      return <Server {...iconProps} />
    default:
      return <Network {...iconProps} />
  }
}

const deviceStyles: Record<DeviceType, {
  border: string
  bg: string
  gradient: string
  text: string
  icon: string
  shadow: string
}> = {
  host: {
    border: 'border-blue-400',
    bg: 'bg-gradient-to-br from-blue-600 to-blue-800',
    gradient: 'bg-blue-500',
    text: 'text-blue-100',
    icon: 'text-blue-200',
    shadow: 'shadow-blue-500/50'
  },
  switch: {
    border: 'border-emerald-400',
    bg: 'bg-gradient-to-br from-emerald-600 to-emerald-800',
    gradient: 'bg-emerald-500',
    text: 'text-emerald-100',
    icon: 'text-emerald-200',
    shadow: 'shadow-emerald-500/50'
  },
  router: {
    border: 'border-purple-400',
    bg: 'bg-gradient-to-br from-purple-600 to-purple-800',
    gradient: 'bg-purple-500',
    text: 'text-purple-100',
    icon: 'text-purple-200',
    shadow: 'shadow-purple-500/50'
  },
  ap: {
    border: 'border-orange-400',
    bg: 'bg-gradient-to-br from-orange-600 to-orange-800',
    gradient: 'bg-orange-500',
    text: 'text-orange-100',
    icon: 'text-orange-200',
    shadow: 'shadow-orange-500/50'
  },
  station: {
    border: 'border-pink-400',
    bg: 'bg-gradient-to-br from-pink-600 to-pink-800',
    gradient: 'bg-pink-500',
    text: 'text-pink-100',
    icon: 'text-pink-200',
    shadow: 'shadow-pink-500/50'
  },
  p4switch: {
    border: 'border-amber-400',
    bg: 'bg-gradient-to-br from-amber-600 to-amber-800',
    gradient: 'bg-amber-500',
    text: 'text-amber-100',
    icon: 'text-amber-200',
    shadow: 'shadow-amber-500/50'
  },
  controller: {
    border: 'border-indigo-400',
    bg: 'bg-gradient-to-br from-indigo-600 to-indigo-800',
    gradient: 'bg-indigo-500',
    text: 'text-indigo-100',
    icon: 'text-indigo-200',
    shadow: 'shadow-indigo-500/50'
  },
}

export const DeviceNode = memo(({ data, selected }: NodeProps) => {
  const deviceType = data.deviceType as DeviceType
  const style = deviceStyles[deviceType] || deviceStyles.host
  const isController = deviceType === 'controller'
  const overlay = data?.overlay && typeof data.overlay === 'object' ? (data.overlay as any) : null
  const overlayFill = overlay?.fill as string | undefined
  const overlayText = overlay?.text as string | undefined
  const overlayBorder = overlay?.border as string | undefined
  const overlayBadge = overlay?.badge as string | undefined

  return (
    <div className="relative group">
      {/* Node Container */}
      <div
        className={`
          relative
          ${overlay ? '' : `${style.bg} ${style.border}`} 
          border-2 rounded-xl
          ${selected ? 'ring-4 ring-yellow-400 scale-105' : 'ring-0'}
          shadow-xl ${overlay ? '' : style.shadow}
          transition-all duration-200
          hover:scale-105 hover:shadow-2xl
          min-w-[150px] max-w-[220px]
        `}
        style={
          overlay
            ? {
                backgroundImage: 'none',
                backgroundColor: overlayFill || '#111827',
                borderColor: overlayBorder || '#111827',
              }
            : undefined
        }
      >
        {/* Top Accent Bar */}
        <div
          className={`h-2 ${overlay ? '' : style.gradient} rounded-t-lg`}
          style={overlay ? { backgroundColor: overlayBorder || overlayFill || '#111827' } : undefined}
        />
        
        {/* Main Content */}
        <div className="px-4 py-3">
          {/* Icon and Label */}
          <div className="flex items-center gap-3 mb-2">
            <div className={`${overlay ? '' : style.icon} p-2.5 rounded-lg bg-black/30 backdrop-blur-sm`}>
              <div style={overlay ? { color: overlayText || '#ffffff' } : undefined}>
                <DeviceIcon type={deviceType} className="w-6 h-6" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-bold text-sm truncate drop-shadow-lg" style={overlay ? { color: overlayText || '#ffffff' } : undefined}>
                {data.label}
              </div>
              <div
                className={`${overlay ? '' : style.text} text-xs font-semibold uppercase tracking-wider flex items-center gap-2`}
                style={overlay ? { color: overlayText || '#ffffff' } : undefined}
              >
                <span>{deviceType}</span>
                {overlayBadge && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-black/30 border border-white/20">
                    {overlayBadge}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Controller Info */}
          {isController && data.controllerType && (
            <div className="mt-2 pt-2 border-t border-white/20">
              <div className="text-xs text-white font-medium">
                <span className="opacity-80">Type:</span> {data.controllerType}
              </div>
              {data.ip && (
                <div className="text-xs text-white/80 mt-1 font-mono">
                  {data.ip}:{data.port || 6653}
                </div>
              )}
            </div>
          )}

          {/* Properties Badge */}
          {!isController && data.properties && Object.keys(data.properties).length > 0 && (
            <div className="mt-2 flex items-center gap-1">
              <div className="text-xs px-2.5 py-1 rounded-full bg-black/40 border border-white/30 text-white font-medium">
                {Object.keys(data.properties).length} properties
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Connection Handles */}
      {/* Top Handle */}
      {!isController && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-white !border-2 !border-gray-600 hover:!scale-150 transition-transform"
        />
      )}

      {/* Bottom Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className={`!w-3 !h-3 !border-2 hover:!scale-150 transition-transform ${
          isController ? '!bg-indigo-400 !border-indigo-600' : '!bg-white !border-gray-600'
        }`}
      />

      {/* Side Handles for non-controllers */}
      {!isController && (
        <>
          <Handle
            type="target"
            position={Position.Left}
            className="!w-3 !h-3 !bg-white !border-2 !border-gray-600 hover:!scale-150 transition-transform"
          />
          <Handle
            type="source"
            position={Position.Right}
            className="!w-3 !h-3 !bg-white !border-2 !border-gray-600 hover:!scale-150 transition-transform"
          />
        </>
      )}
    </div>
  )
})

DeviceNode.displayName = 'DeviceNode'
