import { useState } from 'react'
import type { Controller } from '@/types/topology'

interface ControllerConfigProps {
  controller?: Partial<Controller>
  onSave: (config: Partial<Controller>) => void
  onCancel: () => void
}

const controllerTypes = [
  { value: 'osken', label: 'OS-Ken', description: 'Modern Ryu successor' },
  { value: 'ryu', label: 'Ryu', description: 'Classic SDN controller' },
  { value: 'opendaylight', label: 'OpenDaylight', description: 'Enterprise SDN platform' },
  { value: 'onos', label: 'ONOS', description: 'Carrier-grade SDN OS' },
  { value: 'custom', label: 'Custom', description: 'Custom controller' },
]

export default function ControllerConfig({
  controller,
  onSave,
  onCancel,
}: ControllerConfigProps) {
  const [config, setConfig] = useState<Partial<Controller>>({
    name: controller?.name || '',
    controller_type: controller?.controller_type || 'osken',
    ip: controller?.ip || '127.0.0.1',
    port: controller?.port || 6653,
    config: controller?.config || {},
  })

  const handleSave = () => {
    if (!config.name) {
      alert('Controller name is required')
      return
    }
    onSave(config)
  }

  const selectedType = controllerTypes.find((t) => t.value === config.controller_type)

  return (
    <div className="bg-gray-800 rounded-lg p-6 max-w-2xl">
      <h2 className="text-2xl font-bold text-white mb-6">SDN Controller Configuration</h2>

      <div className="space-y-4">
        {/* Controller Name */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Controller Name
          </label>
          <input
            type="text"
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
            placeholder="e.g., c0, main-controller"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Controller Type */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Controller Type
          </label>
          <select
            value={config.controller_type}
            onChange={(e) =>
              setConfig({
                ...config,
                controller_type: e.target.value as Controller['controller_type'],
              })
            }
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            {controllerTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label} - {type.description}
              </option>
            ))}
          </select>
          {selectedType && (
            <p className="text-xs text-gray-500 mt-1">{selectedType.description}</p>
          )}
        </div>

        {/* IP Address */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            IP Address
          </label>
          <input
            type="text"
            value={config.ip}
            onChange={(e) => setConfig({ ...config, ip: e.target.value })}
            placeholder="127.0.0.1"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Controller IP address (use container name for Docker networks)
          </p>
        </div>

        {/* Port */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            OpenFlow Port
          </label>
          <input
            type="number"
            value={config.port}
            onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) })}
            placeholder="6653"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Default: 6653 (OpenFlow), 6633 (legacy)
          </p>
        </div>

        {/* Additional Config */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Additional Configuration (JSON)
          </label>
          <textarea
            value={JSON.stringify(config.config, null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value)
                setConfig({ ...config, config: parsed })
              } catch (err) {
                // Invalid JSON, don't update
              }
            }}
            rows={6}
            placeholder='{\n  "observe_links": true,\n  "wsapi_port": 8080\n}'
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Controller-specific configuration in JSON format
          </p>
        </div>

        {/* OpenFlow Version */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            OpenFlow Version
          </label>
          <select
            value={config.config?.openflow_version || '1.3'}
            onChange={(e) =>
              setConfig({
                ...config,
                config: { ...config.config, openflow_version: e.target.value },
              })
            }
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="1.0">OpenFlow 1.0</option>
            <option value="1.1">OpenFlow 1.1</option>
            <option value="1.2">OpenFlow 1.2</option>
            <option value="1.3">OpenFlow 1.3 (Default)</option>
            <option value="1.4">OpenFlow 1.4</option>
            <option value="1.5">OpenFlow 1.5</option>
          </select>
        </div>

        {/* Observe Links Option */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="observe-links"
            checked={config.config?.observe_links !== false}
            onChange={(e) =>
              setConfig({
                ...config,
                config: { ...config.config, observe_links: e.target.checked },
              })
            }
            className="w-4 h-4 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          />
          <label htmlFor="observe-links" className="text-sm text-gray-300">
            Enable topology discovery (observe links)
          </label>
        </div>

        {/* REST API Option */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="rest-api"
            checked={config.config?.enable_rest_api !== false}
            onChange={(e) =>
              setConfig({
                ...config,
                config: { ...config.config, enable_rest_api: e.target.checked },
              })
            }
            className="w-4 h-4 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
          />
          <label htmlFor="rest-api" className="text-sm text-gray-300">
            Enable REST API
          </label>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-700">
        <button
          onClick={onCancel}
          className="px-6 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Save Controller
        </button>
      </div>

      {/* Info Box */}
      <div className="mt-6 p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg">
        <h4 className="text-sm font-semibold text-blue-400 mb-2">💡 Controller Tips</h4>
        <ul className="text-xs text-gray-400 space-y-1">
          <li>• Controllers manage OpenFlow switches and P4 switches</li>
          <li>• OS-Ken and Ryu support OpenFlow 1.0-1.5</li>
          <li>• OpenDaylight and ONOS provide enterprise features</li>
          <li>• Use container names for IP in Docker networks (e.g., "osken")</li>
          <li>• REST API enables external control and monitoring</li>
        </ul>
      </div>
    </div>
  )
}

