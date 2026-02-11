import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'

export default function TerminalPanel() {
  const { t } = useTranslation()
  const [selectedNode, setSelectedNode] = useState('h1')
  const [command, setCommand] = useState('')
  const [output, setOutput] = useState<string[]>([])

  const executeCommand = () => {
    if (!command.trim()) return
    setOutput([...output, `$ ${command}`, 'Command executed successfully'])
    setCommand('')
  }

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          {t('webshell.title')}
        </h2>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              {t('webshell.device')}
            </label>
            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="input-field"
            >
              <option value="h1">h1 (Host 1)</option>
              <option value="h2">h2 (Host 2)</option>
              <option value="s1">s1 (Switch 1)</option>
              <option value="r1">r1 (Router 1)</option>
            </select>
          </div>

          <div className="flex gap-2">
            {['ping 10.0.0.1', 'ifconfig', 'ip addr', 'route -n'].map((cmd) => (
              <ModernButton
                key={cmd}
                variant="secondary"
                size="sm"
                onClick={() => setCommand(cmd)}
              >
                {cmd}
              </ModernButton>
            ))}
          </div>

          <div className="bg-black dark:bg-gray-950 rounded-lg p-4 font-mono text-sm text-green-400 h-96 overflow-y-auto">
            {output.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
            <div className="flex items-center gap-2 mt-2">
              <span>$</span>
              <input
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && executeCommand()}
                className="flex-1 bg-transparent border-none outline-none text-green-400"
                placeholder={t('webshell.enterCommand')}
                autoFocus
              />
            </div>
          </div>
        </div>
      </ModernCard>
    </div>
  )
}

